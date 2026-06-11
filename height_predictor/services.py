"""
Glue between the API and the pure predictor. Reads (never writes) existing data:
  - posture recovery cm from users.PostureState (the dashboard's canonical recoverable-loss);
  - onboarding defaults (sex, age, parent/current heights) from user_profile.UserProfile.
No engine / ledger / dashboard logic lives here.
"""
from __future__ import annotations

from datetime import date
from typing import Optional


def _safe_float(value, default: Optional[float] = None) -> Optional[float]:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def get_user_posture_recovery_cm(user) -> float:
    """
    Read the already-computed recoverable-loss cm from PostureState. um -> cm is /10000
    (matches posture_questions.views runtime conversion). Never recomputed here.
    """
    try:
        from users.models import PostureState

        ps = PostureState.objects.filter(user=user).first()
        if ps and ps.total_recoverable_loss_um:
            return round(float(ps.total_recoverable_loss_um) / 10000.0, 4)
    except Exception:
        pass
    return 0.0


def _profile_age_years(profile) -> Optional[float]:
    dob = getattr(profile, "birth_date", None) or getattr(profile, "date_of_birth", None)
    if dob:
        try:
            return (date.today() - dob).days / 365.2425
        except Exception:
            pass
    return _safe_float(getattr(profile, "age", None))


def defaults_from_profile(user) -> dict:
    """
    Pull the already-known onboarding values so the client doesn't re-enter them. Returns only
    the keys it can resolve; the caller merges client-supplied values on top.
    """
    out: dict = {}
    try:
        from user_profile.models import UserProfile

        profile = UserProfile.objects.filter(user=user).first()
    except Exception:
        profile = None
    if not profile:
        return out

    sex = str(getattr(profile, "gender", "") or "").strip().lower()
    if sex in ("male", "female"):
        out["sex"] = sex

    age = _profile_age_years(profile)
    if age is not None:
        out["age_years"] = age

    current = _safe_float(getattr(profile, "base_height_cm", None)) or _safe_float(
        getattr(profile, "current_height_cm", None)
    )
    if current:
        out["current_height_cm"] = current

    father = _safe_float(getattr(profile, "father_height_cm", None))
    if father:
        out["father_height_cm"] = father
    mother = _safe_float(getattr(profile, "mother_height_cm", None))
    if mother:
        out["mother_height_cm"] = mother

    return out


_RECOMPUTE_CORE_FIELDS = ("sex", "age_years", "current_height_cm", "father_height_cm", "mother_height_cm")


def recompute_from_profile(user):
    """
    Refresh a user's stored Ultimate Height prediction after their profile changed.

    Sealed-box rule: this only ever runs when a completed prediction already exists. It re-uses the
    maturity/tape answers from that prediction's ``raw_inputs`` and overlays the *current* profile +
    posture values (so an edited height/parent-height/DOB flows through). A new row is written only
    when the recomputed inputs/result actually differ, so repeated profile saves don't spam rows.

    Returns the prediction row used (existing or newly created), or ``None`` if there was nothing to
    refresh / required values are missing. Never raises into the caller.
    """
    try:
        from .models import UltimateHeightPrediction
        from .predictor import MODEL_VERSION, PredictorInputs, predict_optimized_height
    except Exception:
        return None

    try:
        latest = (
            UltimateHeightPrediction.objects.filter(user=user, completed=True)
            .order_by("-computed_at")
            .first()
        )
        if not latest:
            return None

        # Maturity/tape answers come from the last assessment; profile values win for the core fields.
        merged = dict(latest.raw_inputs or {})
        fresh = defaults_from_profile(user)
        merged.update({k: v for k, v in fresh.items() if v not in (None, "")})

        if any(merged.get(f) in (None, "") for f in _RECOMPUTE_CORE_FIELDS):
            return None

        posture_cm = get_user_posture_recovery_cm(user)

        inputs = PredictorInputs(
            sex=merged["sex"],
            age_years=float(merged["age_years"]),
            current_height_cm=float(merged["current_height_cm"]),
            father_height_cm=float(merged["father_height_cm"]),
            mother_height_cm=float(merged["mother_height_cm"]),
            voice_depth=int(merged.get("voice_depth", 0) or 0),
            facial_hair=int(merged.get("facial_hair", 0) or 0),
            body_hair=int(merged.get("body_hair", 0) or 0),
            adams_apple=int(merged.get("adams_apple", 0) or 0),
            menarche_status=int(merged.get("menarche_status", 0) or 0),
            growth_spurt_status=int(merged.get("growth_spurt_status", 0) or 0),
            recent_growth_cm=merged.get("recent_growth_cm"),
            wingspan_cm=merged.get("wingspan_cm"),
            wrist_circumference_cm=merged.get("wrist_circumference_cm"),
            weight_kg=merged.get("weight_kg"),
            shoe_size=merged.get("shoe_size"),
        )

        breakdown = predict_optimized_height(inputs, posture_cm)

        # Skip writing a new row when nothing meaningful changed (avoids row spam on every save).
        if _matches_existing(latest, inputs, posture_cm, breakdown):
            return latest

        return UltimateHeightPrediction.objects.create(
            user=user,
            sex=inputs.sex,
            age_years=inputs.age_years,
            current_height_cm=inputs.current_height_cm,
            father_height_cm=inputs.father_height_cm,
            mother_height_cm=inputs.mother_height_cm,
            voice_depth=inputs.voice_depth,
            facial_hair=inputs.facial_hair,
            body_hair=inputs.body_hair,
            adams_apple=inputs.adams_apple,
            menarche_status=inputs.menarche_status,
            growth_spurt_status=inputs.growth_spurt_status,
            recent_growth_cm=inputs.recent_growth_cm,
            wingspan_cm=inputs.wingspan_cm,
            wrist_circumference_cm=inputs.wrist_circumference_cm,
            weight_kg=inputs.weight_kg,
            shoe_size=inputs.shoe_size,
            posture_recovery_cm=breakdown["posture_recovery_cm"],
            genetic_potential_cm=breakdown["genetic_potential_cm"],
            true_optimized_cm=breakdown["true_optimized_cm"],
            band=breakdown["band"],
            model_version=MODEL_VERSION,
            completed=True,
            raw_inputs={**merged, "recomputed_from": "profile_update"},
            breakdown=breakdown,
        )
    except Exception:
        return None


def _eq(a, b, places: int = 4) -> bool:
    fa, fb = _safe_float(a), _safe_float(b)
    if fa is None or fb is None:
        return fa == fb
    return round(fa, places) == round(fb, places)


def _matches_existing(latest, inputs, posture_cm, breakdown) -> bool:
    return (
        str(latest.sex or "") == str(inputs.sex or "")
        and _eq(latest.age_years, inputs.age_years, 2)
        and _eq(latest.current_height_cm, inputs.current_height_cm)
        and _eq(latest.father_height_cm, inputs.father_height_cm)
        and _eq(latest.mother_height_cm, inputs.mother_height_cm)
        and _eq(latest.posture_recovery_cm, posture_cm)
        and _eq(latest.true_optimized_cm, breakdown["true_optimized_cm"])
    )

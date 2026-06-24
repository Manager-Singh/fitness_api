"""
Exercise Assignment Spec — scoring and selection (Parts 1–2).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from workouts.exercise_assignment_data import (
    BEAST_MODE_CANONICAL_KEYS,
    TEEN_ONLY_HGH_NAMES,
    dedupe_name_key,
    normalize_exercise_name,
    primary_secondary_for_exercise,
    spec_points_for_exercise,
    spec_key_for_name,
)

SegmentLosses = dict[str, float]

_BREAKDOWN_TO_SEGMENT = {
    "spinal_compression": "spinal",
    "posture_collapse": "collapse",
    "pelvic_tilt_back": "pelvic",
    "leg_hamstring": "legs",
}

_SEGMENT_TO_BREAKDOWN = {v: k for k, v in _BREAKDOWN_TO_SEGMENT.items()}
_PILLARS = ("spinal", "collapse", "pelvic", "legs")
_PILLAR_TIE_ORDER = {"spinal": 4, "collapse": 3, "pelvic": 2, "legs": 1}


@dataclass(frozen=True)
class ScoredExercise:
    exercise: Any  # workouts.Exercise
    score: float


def segment_losses_from_breakdown(
    optimization_breakdown: dict | None,
    section3_contract: dict | None = None,
) -> SegmentLosses:
    """Recoverable loss cm per segment for assignment formulas."""
    if section3_contract and section3_contract.get("mode") in ("issue9_visual", "posture_targeting_v1"):
        segs = section3_contract.get("segments") or {}
        if segs:
            return {
                "spinal": float(segs.get("spinal", {}).get("loss_cm", 0) or 0),
                "collapse": float(segs.get("collapse", {}).get("loss_cm", 0) or 0),
                "pelvic": float(segs.get("pelvic", {}).get("loss_cm", 0) or 0),
                "legs": float(segs.get("legs", {}).get("loss_cm", 0) or 0),
            }

    out: SegmentLosses = {"spinal": 0.0, "collapse": 0.0, "pelvic": 0.0, "legs": 0.0}
    if not optimization_breakdown:
        return out
    for key, payload in optimization_breakdown.items():
        seg = _BREAKDOWN_TO_SEGMENT.get(key)
        if not seg or not isinstance(payload, dict):
            continue
        out[seg] = float(payload.get("current_loss_cm", 0) or 0)
    return out


def ranked_segments_from_losses(losses: SegmentLosses) -> list[str]:
    return sorted(
        losses.keys(),
        key=lambda s: (losses.get(s, 0), _PILLAR_TIE_ORDER.get(s, 0)),
        reverse=True,
    )


def _apportion_slots_by_largest_remainder(weights: dict[str, float], count: int) -> dict[str, int]:
    count = max(0, int(count or 0))
    out = {p: 0 for p in _PILLARS}
    if count <= 0:
        return out
    positive = {p: max(0.0, float(weights.get(p, 0) or 0)) for p in _PILLARS}
    total = sum(positive.values())
    if total <= 0:
        ranked = sorted(_PILLARS, key=lambda p: _PILLAR_TIE_ORDER[p], reverse=True)
        for p in ranked[:count]:
            out[p] += 1
        return out
    raw = {p: count * positive[p] / total for p in _PILLARS}
    for p in _PILLARS:
        out[p] = int(raw[p])
    remaining = count - sum(out.values())
    order = sorted(
        _PILLARS,
        key=lambda p: (raw[p] - int(raw[p]), positive[p], _PILLAR_TIE_ORDER[p]),
        reverse=True,
    )
    for p in order[:remaining]:
        out[p] += 1
    return out


def _exercise_pillar_credit_um(exercise: Any) -> dict[str, int]:
    primary, secondary = primary_secondary_for_exercise(exercise)
    pts_um = spec_points_for_exercise(exercise) * 10
    if not primary or pts_um <= 0:
        return {}
    secondary = secondary or primary
    return {
        primary: int(round(pts_um * 0.70)),
        secondary: int(round(pts_um * 0.30)),
    }


def allocate_variable_slots(
    losses: SegmentLosses,
    core_exercises: Sequence[Any],
    *,
    count: int = 4,
    share_pts: float = 6.75,
) -> dict[str, int]:
    """Monday work order §8: baseline-aware largest-remainder slot allocation."""
    remaining_um = {p: int(round(float(losses.get(p, 0) or 0) * 10000)) for p in _PILLARS}
    core_um = {p: 0 for p in _PILLARS}
    primary_trained = set()
    for ex in core_exercises:
        primary, _secondary = primary_secondary_for_exercise(ex)
        if primary:
            primary_trained.add(primary)
        for p, amount in _exercise_pillar_credit_um(ex).items():
            core_um[p] += amount
    baseline_um = {
        p: core_um[p] + (int(round(share_pts * 10)) if p in primary_trained else 0)
        for p in _PILLARS
    }
    net_gap = {p: max(0, remaining_um[p] - baseline_um[p]) for p in _PILLARS}
    if sum(net_gap.values()) <= 0:
        return _apportion_slots_by_largest_remainder(remaining_um, count)
    return _apportion_slots_by_largest_remainder(net_gap, count)


def _pick_for_allocated_pillars(
    pool: Iterable[Any],
    slots_by_pillar: dict[str, int],
    core_exercises: Sequence[Any],
    *,
    exclude: Sequence[Any] = (),
    allow_teen_only: bool = False,
) -> list[Any]:
    blocked_ids = {e.id for e in core_exercises} | {e.id for e in exclude}
    blocked_keys = {
        dedupe_name_key(getattr(e, "name", "") or "")
        for e in list(core_exercises) + list(exclude)
    }
    selected: list[Any] = []

    def _eligible_for(pillar: str) -> list[Any]:
        candidates = []
        for ex in pool:
            if ex.id in blocked_ids:
                continue
            if not allow_teen_only and getattr(ex, "teen_only", False):
                continue
            key = dedupe_name_key(getattr(ex, "name", "") or "")
            if key and key in blocked_keys:
                continue
            primary, secondary = primary_secondary_for_exercise(ex)
            if primary == pillar:
                candidates.append(ex)
        candidates.sort(
            key=lambda ex: (
                spec_points_for_exercise(ex),
                getattr(ex, "potency", 0) or 0,
                normalize_exercise_name(getattr(ex, "name", "") or ""),
            ),
            reverse=True,
        )
        return candidates

    allocation_order: list[str] = []
    for pillar, n in sorted(
        slots_by_pillar.items(),
        key=lambda item: (item[1], _PILLAR_TIE_ORDER.get(item[0], 0)),
        reverse=True,
    ):
        allocation_order.extend([pillar] * int(n))

    for pillar in allocation_order:
        picked = None
        for ex in _eligible_for(pillar):
            picked = ex
            break
        if picked is None:
            # Fallback: secondary match, then any unused posture exercise.
            fallback = []
            for ex in pool:
                if ex.id in blocked_ids:
                    continue
                if not allow_teen_only and getattr(ex, "teen_only", False):
                    continue
                key = dedupe_name_key(getattr(ex, "name", "") or "")
                if key and key in blocked_keys:
                    continue
                primary, secondary = primary_secondary_for_exercise(ex)
                if secondary == pillar or primary:
                    fallback.append(ex)
            fallback.sort(key=lambda ex: spec_points_for_exercise(ex), reverse=True)
            picked = fallback[0] if fallback else None
        if picked is None:
            continue
        selected.append(picked)
        blocked_ids.add(picked.id)
        key = dedupe_name_key(getattr(picked, "name", "") or "")
        if key:
            blocked_keys.add(key)
    return selected


def _pick_hgh_exercises(
    pool: Iterable[Any],
    count: int,
    *,
    exclude: Sequence[Any] = (),
) -> list[Any]:
    blocked_ids = {getattr(e, "id", None) for e in exclude}
    blocked_keys = {
        dedupe_name_key(getattr(e, "name", "") or "")
        for e in exclude
    }
    candidates: list[Any] = []
    seen_keys: set[str] = set()
    for ex in pool:
        if getattr(ex, "id", None) in blocked_ids:
            continue
        key = dedupe_name_key(getattr(ex, "name", "") or "")
        if key and (key in blocked_keys or key in seen_keys):
            continue
        cat = str(getattr(ex, "category", "") or "").lower()
        is_hgh = bool(
            getattr(ex, "teen_only", False)
            or cat == "hgh"
            or key in TEEN_ONLY_HGH_NAMES
        )
        if not is_hgh:
            continue
        candidates.append(ex)
        if key:
            seen_keys.add(key)

    candidates.sort(
        key=lambda ex: (
            getattr(ex, "hgh_score", 0) or 0,
            spec_points_for_exercise(ex),
            getattr(ex, "beast_bonus", 0) or 0,
            normalize_exercise_name(getattr(ex, "name", "") or ""),
        ),
        reverse=True,
    )
    return candidates[:max(0, int(count or 0))]


def get_age_multipliers(age: int) -> tuple[float, float]:
    """Returns (hgh_mult, posture_mult) per Exercise Assignment Spec Part 2."""
    age = int(age)
    if age <= 15:
        return 1.00, 0.70
    if age <= 17:
        return 0.80, 0.85
    if age == 18:
        return 0.65, 1.00
    return 0.45, 1.15  # 19–20


def _segment_match(exercise: Any, losses: SegmentLosses, posture_mult: float = 1.0) -> float:
    return posture_mult * (
        (exercise.spinal_pct or 0) * losses.get("spinal", 0)
        + (exercise.collapse_pct or 0) * losses.get("collapse", 0)
        + (exercise.pelvic_pct or 0) * losses.get("pelvic", 0)
        + (exercise.legs_pct or 0) * losses.get("legs", 0)
    )


def score_adult_exercise(exercise: Any, losses: SegmentLosses, *, is_beast: bool) -> float:
    segment_match = _segment_match(exercise, losses)
    potency = (exercise.potency or 0) * 10
    intensity = (exercise.beast_bonus or 0) * 5 if is_beast else 0
    return (segment_match * 0.60) + (potency * 0.30) + (intensity * 0.10)


def score_teen_recommended(
    exercise: Any, losses: SegmentLosses, hgh_mult: float, posture_mult: float
) -> float:
    segment_match = _segment_match(exercise, losses, posture_mult)
    potency = (exercise.potency or 0) * 10
    hgh = (exercise.hgh_score or 0) * 10 * hgh_mult
    return (segment_match * 0.60) + (potency * 0.25) + (hgh * 0.15)


def score_teen_beast(
    exercise: Any, losses: SegmentLosses, hgh_mult: float, posture_mult: float
) -> float:
    hgh = (exercise.hgh_score or 0) * 10 * hgh_mult
    segment_match = _segment_match(exercise, losses, posture_mult)
    potency = (exercise.potency or 0) * 10
    intensity = (exercise.beast_bonus or 0) * 5
    return (hgh * 0.50) + (segment_match * 0.30) + (potency * 0.10) + (intensity * 0.10)


def _is_scorable(exercise: Any) -> bool:
    return bool(getattr(exercise, "assignment_matrix_ready", False))


def _exclude_core(pool: Iterable[Any], core_exercises: Sequence[Any]) -> list[Any]:
    core_ids = {e.id for e in core_exercises}
    core_names = {normalize_exercise_name(e.name) for e in core_exercises}
    out = []
    for ex in pool:
        if ex.id in core_ids:
            continue
        if normalize_exercise_name(ex.name) in core_names:
            continue
        out.append(ex)
    return out


def _is_beast_mode_eligible(exercise: Any) -> bool:
    key = spec_key_for_name(getattr(exercise, "name", "") or "")
    return bool(key and key in BEAST_MODE_CANONICAL_KEYS)


def _beast_mode_pool(pool: Iterable[Any]) -> list[Any]:
    return [ex for ex in pool if _is_beast_mode_eligible(ex)]


def beast_whitelist_exercises_from_db(ExerciseModel=None):
    """
    Load Section 10.2 beast whitelist rows from DB by canonical spec key.
    Used when the scoring pool list omits them (name/matrix mismatch).
    """
    if ExerciseModel is None:
        from workouts.models import Exercise as ExerciseModel

    found: dict[str, Any] = {}
    base_qs = ExerciseModel.objects.filter(
        teen_only=False,
        spinal_pct__isnull=False,
        potency__isnull=False,
    ).exclude(adult_only=True)
    for ex in base_qs:
        key = spec_key_for_name(getattr(ex, "name", "") or "")
        if key and key in BEAST_MODE_CANONICAL_KEYS:
            found[key] = ex
    missing = BEAST_MODE_CANONICAL_KEYS - set(found)
    if missing:
        for ex in ExerciseModel.objects.filter(teen_only=False):
            key = spec_key_for_name(getattr(ex, "name", "") or "")
            if key in missing:
                found[key] = ex
                missing.discard(key)
            if not missing:
                break
    return list(found.values())


def _beast_candidates(pool: Iterable[Any]) -> list[Any]:
    """Whitelist exercises from pool, else direct DB lookup."""
    wl = _beast_mode_pool(pool)
    if wl:
        return wl
    return beast_whitelist_exercises_from_db()


def _core_dedupe_keys(core_exercises: Sequence[Any]) -> set[str]:
    keys = set()
    for ex in core_exercises:
        k = dedupe_name_key(getattr(ex, "name", "") or "")
        if k:
            keys.add(k)
    return keys


def _select_beast_exercises(
    pool: Iterable[Any],
    losses: SegmentLosses,
    score_fn,
    count: int,
    *,
    core_exercises: Sequence[Any],
    exclude: Sequence[Any] = (),
    reserved_beast: Sequence[Any] = (),
    allow_teen_only: bool = True,
) -> list[Any]:
    """
    Exercise Assignment Spec (Parts 1–2): Beast picks are the top ``count`` from the
    FULL remaining pool scored by the beast formula — NOT a fixed whitelist.

    Adults: ``allow_teen_only=False`` (HGH exercises are teen-only in every document).
    Teens: ``allow_teen_only=True`` so HGH movers (Box Jumps, Mountain Climbers, …)
    are eligible — they dominate the beast formula for younger teens.

    Beast exercise IDs must not already be on core/recommended (UserRoutineExercise
    unique_together is routine+exercise, not per-tier).
    """
    blocked_ids = {e.id for e in core_exercises} | {e.id for e in exclude}
    blocked_keys = {
        dedupe_name_key(getattr(e, "name", "") or "")
        for e in list(core_exercises) + list(exclude)
    }

    candidates: list[Any] = []
    seen_ids: set[int] = set()
    seen_keys: set[str] = set()
    for ex in list(pool) + list(reserved_beast):
        if ex.id in blocked_ids or ex.id in seen_ids:
            continue
        if not allow_teen_only and getattr(ex, "teen_only", False):
            continue
        key = dedupe_name_key(getattr(ex, "name", "") or "")
        if key and (key in blocked_keys or key in seen_keys):
            continue
        seen_ids.add(ex.id)
        if key:
            seen_keys.add(key)
        candidates.append(ex)

    return pick_top_scored(candidates, score_fn, count)


def pick_top_scored(
    pool: Iterable[Any],
    score_fn,
    count: int,
    *,
    exclude: Sequence[Any] = (),
) -> list[Any]:
    exclude_ids = {e.id for e in exclude}
    scored: list[ScoredExercise] = []
    for ex in pool:
        if ex.id in exclude_ids:
            continue
        scored.append(ScoredExercise(exercise=ex, score=score_fn(ex)))
    scored.sort(key=lambda s: s.score, reverse=True)
    return [s.exercise for s in scored[:count]]


def select_adult_recommended_beast(
    pool: Iterable[Any],
    losses: SegmentLosses,
    core_exercises: Sequence[Any],
    *,
    reserved_beast: Sequence[Any] = (),
) -> tuple[list[Any], list[Any]]:
    """Returns (recommended[2], beast[2]) from Exercise queryset/list."""
    slots = allocate_variable_slots(losses, core_exercises, count=4, share_pts=6.75)
    extra = _pick_for_allocated_pillars(
        pool,
        slots,
        core_exercises,
        exclude=reserved_beast,
        allow_teen_only=False,
    )
    recommended = extra[:2]
    beast = extra[2:4]
    _assert_no_teen_only(recommended + beast, "adult")
    return recommended, beast


def select_teen_recommended_beast(
    pool: Iterable[Any],
    losses: SegmentLosses,
    age: int,
    core_exercises: Sequence[Any],
    *,
    reserved_beast: Sequence[Any] = (),
) -> tuple[list[Any], list[Any]]:
    growth_window_open = 13 <= int(age or 0) <= 18
    posture_optimized = sum(max(0.0, float(losses.get(p, 0) or 0)) for p in _PILLARS) <= 0

    if growth_window_open and posture_optimized:
        hgh_extra = _pick_hgh_exercises(pool, 4, exclude=list(core_exercises) + list(reserved_beast))
        return hgh_extra[:2], hgh_extra[2:4]

    slots = allocate_variable_slots(losses, core_exercises, count=4, share_pts=3.0)
    extra = _pick_for_allocated_pillars(
        pool,
        slots,
        core_exercises=core_exercises,
        exclude=reserved_beast,
        allow_teen_only=False,
    )
    if growth_window_open:
        existing = list(core_exercises) + list(reserved_beast) + list(extra)
        guaranteed_hgh = _pick_hgh_exercises(pool, 1, exclude=existing)
        if guaranteed_hgh:
            extra = (extra[:3] + guaranteed_hgh)[:4]

    recommended = extra[:2]
    beast = extra[2:4]
    return recommended, beast


def _assert_no_teen_only(exercises: Sequence[Any], context: str) -> None:
    for ex in exercises:
        if ex.teen_only or normalize_exercise_name(ex.name) in TEEN_ONLY_HGH_NAMES:
            raise ValueError(f"teen_only exercise {ex.name!r} in {context} Rec/Beast")


def adult_scoring_pool_queryset(ExerciseModel):
    return ExerciseModel.objects.filter(
        teen_only=False,
        spinal_pct__isnull=False,
        potency__isnull=False,
    ).exclude(adult_only=True)


def teen_scoring_pool_queryset(ExerciseModel):
    return ExerciseModel.objects.filter(
        spinal_pct__isnull=False,
        potency__isnull=False,
    )

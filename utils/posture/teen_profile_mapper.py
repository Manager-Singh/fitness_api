from datetime import date

from utils.teen_optimized_height import TeenProfile
from utils.posture.height_helpers import safe_float, safe_int
from utils.posture.posture_utils import compute_posture_potential_cm


def _walk_values(payload):
    if isinstance(payload, dict):
        yield payload
        for value in payload.values():
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _walk_values(item)


def _extract_number(payload, keys, default=0.0):
    for node in _walk_values(payload):
        for key in keys:
            if key in node and node[key] not in (None, ""):
                return safe_float(node[key], default)
    return default


def _extract_int(payload, keys, default=0):
    return safe_int(_extract_number(payload, keys, default), default)


def _normalize_stage(value):
    return (value or "").strip().lower()


def _voice_depth_score(value):
    stage = _normalize_stage(value)
    if stage in {"deep", "adult"}:
        return 2
    if stage in {"in_between", "in-between", "mid"}:
        return 1
    return 0


def _hair_progress_score(value):
    stage = _normalize_stage(value)
    if stage in {"full", "heavy"}:
        return 2
    if stage in {"some", "light", "medium"}:
        return 1
    return 0


def _adams_or_menarche_score(value, sex):
    raw = _normalize_stage(value)
    if raw in {"1", "yes", "true", "started", "present"}:
        return 1
    if raw in {"0", "no", "false", "not_started", "absent"}:
        return 0
    # Spec says this input is mandatory in premium flow; if missing, keep conservative.
    return 0


def _profile_age_years_float(profile):
    dob = getattr(profile, "birth_date", None) or getattr(profile, "date_of_birth", None)
    if dob:
        return (date.today() - dob).days / 365.2425
    raw = safe_float(profile.age, 0.0)
    if raw > 0:
        return raw
    return float(safe_int(profile.age, 13))


def map_userprofile_to_teenprofile(profile, posture_breakdown, posture_report=None) -> TeenProfile:
    report_payload = {}
    if posture_report:
        report_payload = {
            "data": posture_report.data or {},
            "raw_request_data": posture_report.raw_request_data or {},
            "t_pose_data": posture_report.t_pose_data or {},
            "front_data": posture_report.front_data or {},
            "side_data": posture_report.side_data or {},
            "back_data": posture_report.back_data or {},
        }

    sex = (profile.gender or "male").lower()
    hair_score = _hair_progress_score(profile.g_p_facial_armpit_hair)

    return TeenProfile(
        sex=sex,

        age_years=_profile_age_years_float(profile),
        age_months=0,

        current_height_cm=safe_float(getattr(profile, "base_height_cm", None) or profile.current_height_cm),
        father_height_cm=safe_float(profile.father_height_cm),
        mother_height_cm=safe_float(profile.mother_height_cm),

        height_change_12m=profile.g_p_height_change or "0-1",
        shoe_pant_growth=profile.g_p_shoe_pant_growth or "stable",
        voice_stage=profile.g_p_voice_stage or "in_between",
        hair_stage=profile.g_p_facial_armpit_hair or "some",
        looks_vs_peers=profile.g_p_looks or "same",
        last_scan=profile.last_scan or None,

        posture_potential_cm=compute_posture_potential_cm(posture_breakdown),
        voice_depth_score=_voice_depth_score(profile.g_p_voice_stage),
        facial_hair_score=hair_score if sex == "male" else 0,
        axillary_hair_score=hair_score,
        adams_apple_score=_adams_or_menarche_score(
            getattr(profile, "g_p_adams_apple_or_menarche", None),
            sex,
        ),
        wingspan_cm=_extract_number(report_payload, ["wingspan_cm"], default=0.0),
        scan_density_result=_extract_int(
            report_payload,
            ["scan_density_result"],
            default=1,
        ),
        collapse_score=_extract_number(report_payload, ["collapse_score"], default=0.0),
        pelvic_score=_extract_number(report_payload, ["pelvic_score"], default=0.0),
        leg_ham_score=_extract_number(
            report_payload,
            ["leg_ham_score", "leg_hamstring_score"],
            default=0.0,
        ),
        spinal_score=_extract_number(report_payload, ["spinal_score"], default=0.0),
    )

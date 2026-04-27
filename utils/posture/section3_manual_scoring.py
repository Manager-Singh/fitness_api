import json
from utils.posture.height_helpers import clamp, safe_float
from utils.posture.height_constants import (
    POSTURE_SEGMENT_DISTRIBUTION_RATIO,
    POSTURE_SEGMENT_MAX_LOSS_CM,
    posture_segment_opt_pct,
)


def _normalize_answer(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip().lower()
    return str(value).strip().lower()


def _parse_options(value):
    """
    Options are typically stored as a JSON list string (e.g. '["Often","Sometimes","Rarely"]').
    This helper is defensive and returns a best-effort list of strings.
    """
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        raw = value.strip()
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(v) for v in parsed]
        except Exception:
            pass
        return [raw]
    return [str(value)]


def _letter_for_option_index(idx: int) -> str:
    letters = ["A", "B", "C", "D", "E"]
    return letters[idx] if 0 <= idx < len(letters) else ""


def _coerce_to_letters(value, options=None):
    """
    Convert stored answers into A/B/C/D/E letters.

    Supported inputs:
    - Already letter-coded: "A", "B", "A) ..." etc.
    - Text labels: "Often", "Yes, it's obvious", etc., mapped by matching against `options`.
    - Lists / JSON list strings (multi-select), mapped elementwise.
    """
    # First, use the existing strict letter extraction.
    direct = _extract_letters(value)
    if direct:
        return direct

    opts = _parse_options(options)
    if not opts:
        return []

    # Build normalized option lookup: option_text -> index
    norm_to_idx = {}
    for i, opt in enumerate(opts):
        norm_to_idx[_normalize_answer(opt)] = i

    # Normalize the incoming value(s) to compare against options.
    if value is None:
        vals = []
    elif isinstance(value, list):
        vals = value
    elif isinstance(value, str):
        raw = value.strip()
        try:
            parsed = json.loads(raw)
            vals = parsed if isinstance(parsed, list) else [raw]
        except Exception:
            vals = [raw]
    else:
        vals = [value]

    out = []
    for item in vals:
        key = _normalize_answer(item)
        if not key:
            continue
        if key in norm_to_idx:
            out.append(_letter_for_option_index(norm_to_idx[key]))
            continue

        # Common case: stored as full label but with leading letter-like prefix stripped/added.
        # If an option is "A) ..." and value is "...", or vice versa, try substring match.
        for opt_norm, idx in norm_to_idx.items():
            if key == opt_norm:
                out.append(_letter_for_option_index(idx))
                break
        else:
            for opt_norm, idx in norm_to_idx.items():
                if key in opt_norm or opt_norm in key:
                    out.append(_letter_for_option_index(idx))
                    break

    return [x for x in out if x]


def _extract_letters(value):
    """
    Supports:
    - "A", "B", ...
    - "A) Yes"
    - ["A", "B"]
    - JSON list string like '["A","B"]'
    """
    if value is None:
        return []

    if isinstance(value, list):
        vals = value
    elif isinstance(value, str):
        raw = value.strip()
        try:
            parsed = json.loads(raw)
            vals = parsed if isinstance(parsed, list) else [raw]
        except Exception:
            vals = [raw]
    else:
        vals = [value]

    out = []
    for item in vals:
        txt = _normalize_answer(item)
        if not txt:
            continue
        letter = txt[0]
        if letter in {"a", "b", "c", "d", "e"}:
            out.append(letter.upper())
    return out


def _pick_single(value):
    letters = _extract_letters(value)
    return letters[0] if letters else ""


def _pick_single_with_options(value, options=None):
    letters = _coerce_to_letters(value, options=options)
    return letters[0] if letters else ""


def _pick_multi_with_options(value, options=None):
    return _coerce_to_letters(value, options=options)


def build_section3_manual_breakdown(posture_q):
    """
    Spec section 3 scoring:
    - Q6 reversed scoring.
    - Q3 multi-select with cap 0.80.
    - Raw clamp to [1.0, 5.5].
    """
    q1 = _pick_single_with_options(
        getattr(posture_q, "forward_head_posture_answer", None),
        options=getattr(posture_q, "forward_head_posture_options", None),
    )
    q2 = _pick_single_with_options(
        getattr(posture_q, "gap_between_your_lower_back_answer", None),
        options=getattr(posture_q, "gap_between_your_lower_back_options", None),
    )
    q3 = _pick_multi_with_options(
        getattr(posture_q, "tightness_or_discomfort_answer", None),
        options=getattr(posture_q, "tightness_or_discomfort_options", None),
    )
    q4 = _pick_single_with_options(
        getattr(posture_q, "slouch_when_standing_or_sitting_answer", None),
        options=getattr(posture_q, "slouch_when_standing_or_sitting_options", None),
    )
    q5 = _pick_single_with_options(
        getattr(posture_q, "feel_noticeably_shorter_end_of_day_compare_to_morning_answer", None),
        options=getattr(posture_q, "feel_noticeably_shorter_end_of_day_compare_to_morning_options", None),
    )
    q6 = _pick_single_with_options(
        getattr(posture_q, "perfectly_aligned_and_decompressed_answer", None),
        options=getattr(posture_q, "perfectly_aligned_and_decompressed_options", None),
    )
    q7 = _pick_single_with_options(
        getattr(posture_q, "flexible_in_your_hamstrings_and_hips_answer", None),
        options=getattr(posture_q, "flexible_in_your_hamstrings_and_hips_options", None),
    )
    q8 = _pick_single_with_options(
        getattr(posture_q, "active_your_core_during_daily_task_answer", None),
        options=getattr(posture_q, "active_your_core_during_daily_task_options", None),
    )

    q1_score = {"A": 0.80, "B": 0.40, "C": 0.0}.get(q1, 0.0)
    q2_score = {"A": 0.70, "B": 0.35, "C": 0.0}.get(q2, 0.0)
    q4_score = {"A": 0.70, "B": 0.35, "C": 0.0}.get(q4, 0.0)
    q5_score = {"A": 0.60, "B": 0.30, "C": 0.0}.get(q5, 0.0)
    # Reversed note in spec: A mild, C severe.
    q6_score = {"A": 0.70, "B": 1.10, "C": 1.50, "D": 0.60}.get(q6, 0.0)
    q7_score = {"A": 0.50, "B": 0.25, "C": 0.0}.get(q7, 0.0)
    q8_score = {"A": 0.50, "B": 0.25, "C": 0.0}.get(q8, 0.0)

    q3_map = {"A": 0.25, "B": 0.25, "C": 0.15, "D": 0.15, "E": 0.0}
    q3_score = sum(q3_map.get(letter, 0.0) for letter in set(q3))
    q3_score = clamp(q3_score, 0.0, 0.80)

    raw_total = (
        q1_score + q2_score + q3_score + q4_score + q5_score + q6_score + q7_score + q8_score
    )
    total_recoverable_loss = clamp(raw_total, 1.0, 5.5)

    breakdown = {}
    for seg, ratio in POSTURE_SEGMENT_DISTRIBUTION_RATIO.items():
        max_loss = POSTURE_SEGMENT_MAX_LOSS_CM[seg]
        current_loss = clamp(total_recoverable_loss * ratio, 0.0, max_loss)
        breakdown[seg] = {
            "current_loss_cm": round(current_loss, 2),
            "max_loss_cm": max_loss,
            "percent_optimized": posture_segment_opt_pct(current_loss, max_loss),
        }

    return {
        "raw_score_cm": round(raw_total, 2),
        "total_recoverable_loss_cm": round(safe_float(total_recoverable_loss), 2),
        "optimization_breakdown": breakdown,
    }

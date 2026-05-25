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
    spec_key_for_name,
)

SegmentLosses = dict[str, float]

_BREAKDOWN_TO_SEGMENT = {
    "spinal_compression": "spinal",
    "posture_collapse": "collapse",
    "pelvic_tilt_back": "pelvic",
    "leg_hamstring": "legs",
}


@dataclass(frozen=True)
class ScoredExercise:
    exercise: Any  # workouts.Exercise
    score: float


def segment_losses_from_breakdown(
    optimization_breakdown: dict | None,
    section3_contract: dict | None = None,
) -> SegmentLosses:
    """Recoverable loss cm per segment for assignment formulas."""
    if section3_contract and section3_contract.get("mode") == "issue9_visual":
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
    tie = {"spinal": 4, "collapse": 3, "pelvic": 2, "legs": 1}
    return sorted(
        losses.keys(),
        key=lambda s: (losses.get(s, 0), tie.get(s, 0)),
        reverse=True,
    )


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
) -> list[Any]:
    """
    Section 10.2: pick ``count`` beast-tier exercises from the whitelist.

    Prefer whitelist exercises not already in core (by canonical name). Adult/teen
    core programs include most whitelist moves; if none remain, still assign the top
    scored whitelist picks so Beast slots are never empty.
    """
    exclude_ids = {e.id for e in exclude}
    core_keys = _core_dedupe_keys(core_exercises)
    whitelist = [ex for ex in _beast_mode_pool(pool) if ex.id not in exclude_ids]

    non_core = [ex for ex in whitelist if dedupe_name_key(ex.name) not in core_keys]
    beast = pick_top_scored(non_core, score_fn, count)
    if len(beast) >= count:
        return beast

    already = {e.id for e in beast}
    fallback_pool = [ex for ex in whitelist if ex.id not in already]
    extra = pick_top_scored(fallback_pool, score_fn, count - len(beast))
    return beast + extra


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
) -> tuple[list[Any], list[Any]]:
    """Returns (recommended[2], beast[2]) from Exercise queryset/list."""
    remaining = _exclude_core(pool, core_exercises)
    remaining = [ex for ex in remaining if not ex.teen_only]

    recommended = pick_top_scored(
        remaining,
        lambda ex: score_adult_exercise(ex, losses, is_beast=False),
        2,
    )
    beast = _select_beast_exercises(
        pool,
        losses,
        lambda ex: score_adult_exercise(ex, losses, is_beast=True),
        2,
        core_exercises=core_exercises,
        exclude=recommended,
    )
    _assert_no_teen_only(recommended + beast, "adult")
    for ex in beast:
        if not _is_beast_mode_eligible(ex):
            raise ValueError(f"non-beast exercise {ex.name!r} assigned to beast tier")
    return recommended, beast


def select_teen_recommended_beast(
    pool: Iterable[Any],
    losses: SegmentLosses,
    age: int,
    core_exercises: Sequence[Any],
) -> tuple[list[Any], list[Any]]:
    hgh_mult, posture_mult = get_age_multipliers(age)
    remaining = _exclude_core(pool, core_exercises)

    recommended = pick_top_scored(
        remaining,
        lambda ex: score_teen_recommended(ex, losses, hgh_mult, posture_mult),
        2,
    )
    beast = _select_beast_exercises(
        pool,
        losses,
        lambda ex: score_teen_beast(ex, losses, hgh_mult, posture_mult),
        2,
        core_exercises=core_exercises,
        exclude=recommended,
    )
    for ex in beast:
        if not _is_beast_mode_eligible(ex):
            raise ValueError(f"non-beast exercise {ex.name!r} assigned to beast tier")
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

"""Default sets/qty/unit when VariantExercise row is missing (EXERCISE_SPEC_SHEET.md)."""

from workouts.models import Unit

DEFAULT_PRESCRIPTION = {
    "sets": 2,
    "quantity_min": 10,
    "quantity_max": None,
    "unit": Unit.REPS,
}

EXERCISE_PRESCRIPTIONS = {
    # Posture — reps
    "bird-dog": {"sets": 2, "quantity_min": 12, "quantity_max": None, "unit": Unit.REPS, "per_side": True},
    "cat-cow stretch": {"sets": 2, "quantity_min": 12, "quantity_max": None, "unit": Unit.REPS},
    "chin tucks": {"sets": 2, "quantity_min": 15, "quantity_max": None, "unit": Unit.REPS},
    "foam roller thoracic extension": {"sets": 2, "quantity_min": 12, "quantity_max": None, "unit": Unit.REPS},
    "glute bridges": {"sets": 2, "quantity_min": 20, "quantity_max": None, "unit": Unit.REPS},
    "pelvic tilts": {"sets": 2, "quantity_min": 20, "quantity_max": None, "unit": Unit.REPS},
    "wall angels": {"sets": 2, "quantity_min": 15, "quantity_max": None, "unit": Unit.REPS},
    # Posture — holds (timer)
    "butterfly stretch": {"sets": 2, "quantity_min": 30, "quantity_max": None, "unit": Unit.SECS},
    "child's pose": {"sets": 2, "quantity_min": 40, "quantity_max": None, "unit": Unit.SECS},
    "child's pose with arm walks": {"sets": 2, "quantity_min": 40, "quantity_max": None, "unit": Unit.SECS},
    "cobra stretch": {"sets": 2, "quantity_min": 30, "quantity_max": None, "unit": Unit.SECS},
    "decompression hang": {"sets": 2, "quantity_min": 45, "quantity_max": None, "unit": Unit.SECS},
    "deep squat hold": {"sets": 2, "quantity_min": 45, "quantity_max": None, "unit": Unit.SECS},
    "doorway chest stretch": {"sets": 2, "quantity_min": 30, "quantity_max": None, "unit": Unit.SECS},
    "hamstring stretch": {"sets": 2, "quantity_min": 30, "quantity_max": None, "unit": Unit.SECS, "per_side": True, "per_side_word": "leg"},
    "hip flexor stretch": {"sets": 2, "quantity_min": 30, "quantity_max": None, "unit": Unit.SECS, "per_side": True},
    "plank": {"sets": 2, "quantity_min": 45, "quantity_max": None, "unit": Unit.SECS},
    "seated forward fold": {"sets": 2, "quantity_min": 30, "quantity_max": None, "unit": Unit.SECS},
    "spinal twist stretch": {"sets": 2, "quantity_min": 30, "quantity_max": None, "unit": Unit.SECS, "per_side": True},
    "superman hold": {"sets": 2, "quantity_min": 30, "quantity_max": None, "unit": Unit.SECS},
    "tadasana (mountain pose)": {"sets": 2, "quantity_min": 30, "quantity_max": None, "unit": Unit.SECS},
    # HGH — reps
    "box jumps / jump squats": {"sets": 2, "quantity_min": 12, "quantity_max": None, "unit": Unit.REPS},
    "bodyweight squats": {"sets": 2, "quantity_min": 25, "quantity_max": None, "unit": Unit.REPS},
    "lunges": {"sets": 2, "quantity_min": 12, "quantity_max": None, "unit": Unit.REPS, "per_side": True, "per_side_word": "leg"},
    "squats": {"sets": 2, "quantity_min": 20, "quantity_max": None, "unit": Unit.REPS},
    # HGH — timers
    "hgh boost (sprint & burpees)": {"sets": 2, "quantity_min": 30, "quantity_max": None, "unit": Unit.SECS},
    "high knees": {"sets": 2, "quantity_min": 40, "quantity_max": None, "unit": Unit.SECS},
    "jump rope": {"sets": 2, "quantity_min": 60, "quantity_max": None, "unit": Unit.SECS},
    "mountain climbers": {"sets": 2, "quantity_min": 40, "quantity_max": None, "unit": Unit.SECS},
    # Legacy aliases
    "hanging from bar": {"sets": 2, "quantity_min": 45, "quantity_max": None, "unit": Unit.SECS},
    "box jumps": {"sets": 2, "quantity_min": 12, "quantity_max": None, "unit": Unit.REPS},
}


def prescription_for_exercise_name(name: str) -> dict:
    from workouts.exercise_assignment_data import normalize_exercise_name, spec_key_for_name

    key = spec_key_for_name(name) or normalize_exercise_name(name)
    pres = dict(EXERCISE_PRESCRIPTIONS.get(key, DEFAULT_PRESCRIPTION))
    pres.pop("per_side", None)
    pres.pop("per_side_word", None)
    return pres

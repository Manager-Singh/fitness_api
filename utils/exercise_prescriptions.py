"""Default sets/qty/unit when VariantExercise row is missing on a variant."""

from workouts.models import Unit

DEFAULT_PRESCRIPTION = {
    "sets": 2,
    "quantity_min": 10,
    "quantity_max": None,
    "unit": Unit.REPS,
}

EXERCISE_PRESCRIPTIONS = {
    "decompression hang": {"sets": 2, "quantity_min": 30, "quantity_max": 60, "unit": Unit.SECS},
    "hanging from bar": {"sets": 2, "quantity_min": 30, "quantity_max": 60, "unit": Unit.SECS},
    "cobra stretch": {"sets": 2, "quantity_min": 30, "quantity_max": None, "unit": Unit.SECS},
    "hip flexor stretch": {"sets": 2, "quantity_min": 30, "quantity_max": None, "unit": Unit.SECS},
    "wall angels": {"sets": 2, "quantity_min": 12, "quantity_max": None, "unit": Unit.REPS},
    "glute bridges": {"sets": 3, "quantity_min": 15, "quantity_max": None, "unit": Unit.REPS},
    "jump rope": {"sets": 2, "quantity_min": 60, "quantity_max": None, "unit": Unit.SECS},
    "bodyweight squats": {"sets": 3, "quantity_min": 20, "quantity_max": None, "unit": Unit.REPS},
    "chin tucks": {"sets": 3, "quantity_min": 10, "quantity_max": None, "unit": Unit.REPS},
    "plank": {"sets": 2, "quantity_min": 45, "quantity_max": 60, "unit": Unit.SECS},
    "pelvic tilts": {"sets": 3, "quantity_min": 15, "quantity_max": None, "unit": Unit.REPS},
}


def prescription_for_exercise_name(name: str) -> dict:
    from workouts.exercise_assignment_data import normalize_exercise_name, spec_key_for_name

    key = spec_key_for_name(name) or normalize_exercise_name(name)
    return dict(EXERCISE_PRESCRIPTIONS.get(key, DEFAULT_PRESCRIPTION))

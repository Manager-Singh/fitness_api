"""
Exercise Assignment Spec (Parts 1–2) — canonical metadata for backfill and scoring.
Keys are normalized lookup names (lowercase); display `name` is the canonical label.
"""

TEEN_ONLY_HGH_NAMES = frozenset({
    "box jumps",
    "high knees",
    "mountain climbers",
    "jump rope",
    "bodyweight squats",
    "lunges",
})

# canonical_key -> spec row
EXERCISE_ASSIGNMENT_SPEC = {
    "decompression hang": {
        "name": "Decompression Hang",
        "age_group": "both",
        "spinal_pct": 80, "collapse_pct": 15, "pelvic_pct": 5, "legs_pct": 0,
        "potency": 10, "hgh_score": 2, "beast_bonus": 3, "teen_only": False,
        "category": "posture", "points": 9,
    },
    "cobra stretch": {
        "name": "Cobra Stretch",
        "age_group": "both",
        "spinal_pct": 70, "collapse_pct": 25, "pelvic_pct": 5, "legs_pct": 0,
        "potency": 8, "hgh_score": 1, "beast_bonus": 1, "teen_only": False,
        "category": "posture", "points": 7,
    },
    "hip flexor stretch": {
        "name": "Hip Flexor Stretch",
        "age_group": "both",
        "spinal_pct": 10, "collapse_pct": 0, "pelvic_pct": 75, "legs_pct": 15,
        "potency": 9, "hgh_score": 1, "beast_bonus": 1, "teen_only": False,
        "category": "posture", "points": 7,
    },
    "wall angels": {
        "name": "Wall Angels",
        "age_group": "both",
        "spinal_pct": 30, "collapse_pct": 65, "pelvic_pct": 5, "legs_pct": 0,
        "potency": 9, "hgh_score": 1, "beast_bonus": 2, "teen_only": False,
        "category": "posture", "points": 7,
    },
    "glute bridges": {
        "name": "Glute Bridges",
        "age_group": "both",
        "spinal_pct": 10, "collapse_pct": 0, "pelvic_pct": 70, "legs_pct": 20,
        "potency": 8, "hgh_score": 3, "beast_bonus": 2, "teen_only": False,
        "category": "posture", "points": 7,
    },
    "cat-cow stretch": {
        "name": "Cat-Cow Stretch",
        "age_group": "both",
        "spinal_pct": 60, "collapse_pct": 30, "pelvic_pct": 10, "legs_pct": 0,
        "potency": 6, "hgh_score": 1, "beast_bonus": 1, "teen_only": False,
        "category": "posture", "points": 6,
    },
    "hamstring stretch": {
        "name": "Hamstring Stretch",
        "age_group": "both",
        "spinal_pct": 50, "collapse_pct": 30, "pelvic_pct": 65, "legs_pct": 5,
        "potency": 7, "hgh_score": 1, "beast_bonus": 0, "teen_only": False,
        "category": "posture", "points": 6,
    },
    "tadasana (mountain pose)": {
        "name": "Tadasana (Mountain Pose)",
        "age_group": "both",
        "spinal_pct": 40, "collapse_pct": 40, "pelvic_pct": 15, "legs_pct": 5,
        "potency": 5, "hgh_score": 1, "beast_bonus": 0, "teen_only": False,
        "category": "posture", "points": 6,
    },
    "doorway chest stretch": {
        "name": "Doorway Chest Stretch",
        "age_group": "both",
        "spinal_pct": 20, "collapse_pct": 75, "pelvic_pct": 5, "legs_pct": 0,
        "potency": 8, "hgh_score": 1, "beast_bonus": 1, "teen_only": False,
        "category": "posture", "points": 6,
    },
    "child's pose with arm walks": {
        "name": "Child's Pose with Arm Walks",
        "age_group": "both",
        "spinal_pct": 50, "collapse_pct": 35, "pelvic_pct": 15, "legs_pct": 0,
        "potency": 6, "hgh_score": 1, "beast_bonus": 0, "teen_only": False,
        "category": "posture", "points": 6,
    },
    "spinal twist stretch": {
        "name": "Spinal Twist Stretch",
        "age_group": "both",
        "spinal_pct": 70, "collapse_pct": 15, "pelvic_pct": 15, "legs_pct": 0,
        "potency": 6, "hgh_score": 1, "beast_bonus": 1, "teen_only": False,
        "category": "posture", "points": 6,
    },
    "butterfly stretch": {
        "name": "Butterfly Stretch",
        "age_group": "both",
        "spinal_pct": 50, "collapse_pct": 70, "pelvic_pct": 25, "legs_pct": 5,
        "potency": 5, "hgh_score": 1, "beast_bonus": 0, "teen_only": False,
        "category": "posture", "points": 5,
    },
    "chin tucks": {
        "name": "Chin Tucks",
        "age_group": "both",
        "spinal_pct": 65, "collapse_pct": 30, "pelvic_pct": 5, "legs_pct": 0,
        "potency": 6, "hgh_score": 1, "beast_bonus": 0, "teen_only": False,
        "category": "posture", "points": 5,
    },
    "superman hold": {
        "name": "Superman Hold",
        "age_group": "both",
        "spinal_pct": 45, "collapse_pct": 50, "pelvic_pct": 5, "legs_pct": 0,
        "potency": 7, "hgh_score": 4, "beast_bonus": 2, "teen_only": False,
        "category": "posture", "points": 7,
    },
    "plank": {
        "name": "Plank",
        "age_group": "both",
        "spinal_pct": 35, "collapse_pct": 25, "pelvic_pct": 35, "legs_pct": 5,
        "potency": 7, "hgh_score": 5, "beast_bonus": 3, "teen_only": False,
        "category": "posture", "points": 7,
    },
    "deep squat hold": {
        "name": "Deep Squat Hold",
        "age_group": "both",
        "spinal_pct": 10, "collapse_pct": 5, "pelvic_pct": 40, "legs_pct": 45,
        "potency": 8, "hgh_score": 4, "beast_bonus": 2, "teen_only": False,
        "category": "posture", "points": 8,
    },
    "box jumps": {
        "name": "Box Jumps",
        "age_group": "teen",
        "spinal_pct": 10, "collapse_pct": 5, "pelvic_pct": 30, "legs_pct": 55,
        "potency": 7, "hgh_score": 10, "beast_bonus": 3, "teen_only": True,
        "category": "hgh", "points": 9,
    },
    "high knees": {
        "name": "High Knees",
        "age_group": "teen",
        "spinal_pct": 5, "collapse_pct": 10, "pelvic_pct": 25, "legs_pct": 60,
        "potency": 6, "hgh_score": 9, "beast_bonus": 2, "teen_only": True,
        "category": "hgh", "points": 8,
    },
    "mountain climbers": {
        "name": "Mountain Climbers",
        "age_group": "teen",
        "spinal_pct": 10, "collapse_pct": 15, "pelvic_pct": 45, "legs_pct": 30,
        "potency": 6, "hgh_score": 9, "beast_bonus": 3, "teen_only": True,
        "category": "hgh", "points": 8,
    },
    "jump rope": {
        "name": "Jump Rope",
        "age_group": "teen",
        "spinal_pct": 15, "collapse_pct": 10, "pelvic_pct": 20, "legs_pct": 55,
        "potency": 6, "hgh_score": 9, "beast_bonus": 2, "teen_only": True,
        "category": "hgh", "points": 9,
    },
    "bodyweight squats": {
        "name": "Bodyweight Squats",
        "age_group": "teen",
        "spinal_pct": 5, "collapse_pct": 5, "pelvic_pct": 35, "legs_pct": 55,
        "potency": 7, "hgh_score": 8, "beast_bonus": 1, "teen_only": True,
        "category": "hgh", "points": 8,
    },
    "lunges": {
        "name": "Lunges",
        "age_group": "teen",
        "spinal_pct": 5, "collapse_pct": 5, "pelvic_pct": 30, "legs_pct": 60,
        "potency": 6, "hgh_score": 7, "beast_bonus": 1, "teen_only": True,
        "category": "hgh", "points": 7,
    },
    "pelvic tilts": {
        "name": "Pelvic Tilts",
        "age_group": "adult",
        "spinal_pct": 15, "collapse_pct": 10, "pelvic_pct": 70, "legs_pct": 5,
        "potency": 6, "hgh_score": 1, "beast_bonus": 0, "teen_only": False,
        "adult_only": True,
        "category": "posture", "points": 6,
    },
}

# DB name aliases -> canonical spec key
EXERCISE_NAME_ALIASES = {
    "hanging from bar": "decompression hang",
    "hanging form bar": "decompression hang",
    "squats": "bodyweight squats",
    "box jumps / jump squats": "box jumps",
    "jump squats": "box jumps",
    "child's pose w/ arm walks": "child's pose with arm walks",
    "child’s pose with arm walks": "child's pose with arm walks",
    "child's pose with arm walks": "child's pose with arm walks",
    "tadasana / mountain": "tadasana (mountain pose)",
    "tadasana (mountain pose)": "tadasana (mountain pose)",
    "cat-cow": "cat-cow stretch",
    "doorways chest stretch": "doorway chest stretch",
    "mountain climber": "mountain climbers",
}

TEEN_CORE_6_NAMES = [
    "Decompression Hang",
    "Cobra Stretch",
    "Hip Flexor Stretch",
    "Wall Angels",
    "Jump Rope",
    "Bodyweight Squats",
]

# Master spec §4.4 — Core 6 exercise names by age bracket min_age (adults 21+).
ADULT_CORE_6_BY_MIN_AGE = {
    21: [
        "Decompression Hang",
        "Cobra Stretch",
        "Glute Bridges",
        "Hip Flexor Stretch",
        "Wall Angels",
        "Chin Tucks",
    ],
    30: [
        "Decompression Hang",
        "Cobra Stretch",
        "Glute Bridges",
        "Hip Flexor Stretch",
        "Pelvic Tilts",
        "Wall Angels",
    ],
    40: [
        "Decompression Hang",
        "Cobra Stretch",
        "Glute Bridges",
        "Hip Flexor Stretch",
        "Pelvic Tilts",
        "Wall Angels",
    ],
    50: [
        "Decompression Hang",
        "Cobra Stretch",
        "Glute Bridges",
        "Hip Flexor Stretch",
        "Cat-Cow Stretch",
        "Wall Angels",
    ],
    60: [
        "Decompression Hang",
        "Cobra Stretch",
        "Glute Bridges",
        "Hip Flexor Stretch",
        "Cat-Cow Stretch",
        "Wall Angels",
    ],
}

# Posture exercises attachable as rec/beast pool rows on variants (prescriptions + GIFs).
ADULT_POSTURE_POOL_CANONICAL_NAMES = [
    spec["name"]
    for key, spec in EXERCISE_ASSIGNMENT_SPEC.items()
    if not spec.get("teen_only")
]

TEEN_POSTURE_POOL_CANONICAL_NAMES = [
    spec["name"]
    for key, spec in EXERCISE_ASSIGNMENT_SPEC.items()
    if not spec.get("teen_only")
]

TEEN_HGH_POOL_CANONICAL_NAMES = [
    spec["name"]
    for key, spec in EXERCISE_ASSIGNMENT_SPEC.items()
    if spec.get("teen_only")
]


def normalize_exercise_name(name: str) -> str:
    return (name or "").strip().lower()


def spec_key_for_name(name: str) -> str | None:
    key = normalize_exercise_name(name)
    if key in EXERCISE_ASSIGNMENT_SPEC:
        return key
    return EXERCISE_NAME_ALIASES.get(key)


def is_teen_only_exercise(exercise) -> bool:
    """True for HGH teen exclusives (flag or known spec/name)."""
    if getattr(exercise, "teen_only", False):
        return True
    key = spec_key_for_name(getattr(exercise, "name", "") or "")
    return bool(key and key in TEEN_ONLY_HGH_NAMES)


def apply_spec_to_exercise_dict(spec: dict) -> dict:
    """Fields to set on Exercise model from a spec row."""
    return {
        "age_group": spec["age_group"],
        "spinal_pct": spec["spinal_pct"],
        "collapse_pct": spec["collapse_pct"],
        "pelvic_pct": spec["pelvic_pct"],
        "legs_pct": spec["legs_pct"],
        "potency": spec["potency"],
        "hgh_score": spec["hgh_score"],
        "beast_bonus": spec["beast_bonus"],
        "teen_only": spec.get("teen_only", False),
        "adult_only": spec.get("adult_only", False),
    }

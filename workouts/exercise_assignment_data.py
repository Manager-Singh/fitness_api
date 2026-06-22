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
        "spinal_pct": 5, "collapse_pct": 0, "pelvic_pct": 30, "legs_pct": 65,
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
        "spinal_pct": 5, "collapse_pct": 0, "pelvic_pct": 70, "legs_pct": 25,
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
    "hanging from bar": "decompression hang",
    "hanging": "decompression hang",
    "knees-to-chest rock": "knees-to-chest rock",
    "knees to chest rock": "knees-to-chest rock",
    "standing posture reset": "standing posture reset",
    "hamstring hinge": "hamstring hinge",
    "bird dog": "bird dog",
    "dead bug": "dead bug",
    "side plank": "side plank",
    "pigeon pose": "pigeon pose",
    "wall calf stretch": "wall calf stretch",
    "ankle mobility": "ankle mobility",
}

# Monday work order: Recommended/Beast are display labels only, not whitelists.
BEAST_MODE_CANONICAL_KEYS = frozenset()

EXERCISE_ASSIGNMENT_SPEC.update({
    "standing posture reset": {
        "name": "Standing Posture Reset",
        "age_group": "both",
        "spinal_pct": 30, "collapse_pct": 70, "pelvic_pct": 0, "legs_pct": 0,
        "potency": 7, "hgh_score": 1, "beast_bonus": 0, "teen_only": False,
        "category": "posture", "points": 7,
    },
    "knees-to-chest rock": {
        "name": "Knees-to-Chest Rock",
        "age_group": "both",
        "spinal_pct": 70, "collapse_pct": 0, "pelvic_pct": 30, "legs_pct": 0,
        "potency": 7, "hgh_score": 1, "beast_bonus": 0, "teen_only": False,
        "category": "posture", "points": 7,
    },
    "hamstring hinge": {
        "name": "Hamstring Hinge",
        "age_group": "both",
        "spinal_pct": 0, "collapse_pct": 0, "pelvic_pct": 30, "legs_pct": 70,
        "potency": 6, "hgh_score": 1, "beast_bonus": 0, "teen_only": False,
        "category": "posture", "points": 6,
    },
    "bird dog": {
        "name": "Bird Dog",
        "age_group": "both",
        "spinal_pct": 30, "collapse_pct": 0, "pelvic_pct": 70, "legs_pct": 0,
        "potency": 6, "hgh_score": 1, "beast_bonus": 0, "teen_only": False,
        "category": "posture", "points": 6,
    },
    "dead bug": {
        "name": "Dead Bug",
        "age_group": "both",
        "spinal_pct": 30, "collapse_pct": 0, "pelvic_pct": 70, "legs_pct": 0,
        "potency": 6, "hgh_score": 1, "beast_bonus": 0, "teen_only": False,
        "category": "posture", "points": 6,
    },
    "side plank": {
        "name": "Side Plank",
        "age_group": "both",
        "spinal_pct": 0, "collapse_pct": 0, "pelvic_pct": 70, "legs_pct": 30,
        "potency": 5, "hgh_score": 1, "beast_bonus": 0, "teen_only": False,
        "category": "posture", "points": 5,
    },
    "pigeon pose": {
        "name": "Pigeon Pose",
        "age_group": "both",
        "spinal_pct": 0, "collapse_pct": 0, "pelvic_pct": 70, "legs_pct": 30,
        "potency": 5, "hgh_score": 1, "beast_bonus": 0, "teen_only": False,
        "category": "posture", "points": 5,
    },
    "wall calf stretch": {
        "name": "Wall Calf Stretch",
        "age_group": "both",
        "spinal_pct": 0, "collapse_pct": 0, "pelvic_pct": 30, "legs_pct": 70,
        "potency": 4, "hgh_score": 1, "beast_bonus": 0, "teen_only": False,
        "category": "posture", "points": 4,
    },
    "ankle mobility": {
        "name": "Ankle Mobility",
        "age_group": "both",
        "spinal_pct": 0, "collapse_pct": 0, "pelvic_pct": 30, "legs_pct": 70,
        "potency": 4, "hgh_score": 1, "beast_bonus": 0, "teen_only": False,
        "category": "posture", "points": 4,
    },
})

SPEC_PRIMARY_SECONDARY = {
    "decompression hang": ("spinal", "collapse"),
    "wall angels": ("collapse", "spinal"),
    "glute bridges": ("pelvic", "legs"),
    "hip flexor stretch": ("pelvic", "legs"),
    "cobra stretch": ("spinal", "pelvic"),
    "knees-to-chest rock": ("spinal", "pelvic"),
    "standing posture reset": ("collapse", "spinal"),
    "cat-cow stretch": ("spinal", "pelvic"),
    "hamstring stretch": ("legs", "pelvic"),
    "hamstring hinge": ("legs", "pelvic"),
    "tadasana (mountain pose)": ("collapse", "spinal"),
    "doorway chest stretch": ("collapse", "spinal"),
    "child's pose with arm walks": ("spinal", "collapse"),
    "spinal twist stretch": ("spinal", "pelvic"),
    "pelvic tilts": ("pelvic", "spinal"),
    "bird dog": ("pelvic", "spinal"),
    "dead bug": ("pelvic", "spinal"),
    "chin tucks": ("collapse", "spinal"),
    "butterfly stretch": ("legs", "pelvic"),
    "side plank": ("pelvic", "legs"),
    "pigeon pose": ("pelvic", "legs"),
    "wall calf stretch": ("legs", "pelvic"),
    "ankle mobility": ("legs", "pelvic"),
}

TEEN_CORE_BASE_NAMES = [
    "Jump Rope",
    "Decompression Hang",
    "Wall Angels",
    "Glute Bridges",
    "Hamstring Stretch",
]

TEEN_CORE_6_NAMES = TEEN_CORE_BASE_NAMES

# Master spec §4.4 — Core 6 exercise names by age bracket min_age (adults 21+).
ADULT_CORE_6_BY_MIN_AGE = {
    21: [
        "Decompression Hang",
        "Cobra Stretch",
        "Wall Angels",
        "Tadasana (Mountain Pose)",
        "Glute Bridges",
        "Hamstring Stretch",
    ],
    30: [
        "Decompression Hang",
        "Cobra Stretch",
        "Wall Angels",
        "Chin Tucks",
        "Glute Bridges",
        "Hamstring Stretch",
    ],
    40: [
        "Decompression Hang",
        "Cobra Stretch",
        "Wall Angels",
        "Chin Tucks",
        "Glute Bridges",
        "Hamstring Stretch",
    ],
    50: [
        "Decompression Hang",
        "Cobra Stretch",
        "Wall Angels",
        "Cat-Cow Stretch",
        "Hip Flexor Stretch",
        "Wall Calf Stretch",
    ],
    60: [
        "Decompression Hang",
        "Cobra Stretch",
        "Wall Angels",
        "Cat-Cow Stretch",
        "Hip Flexor Stretch",
        "Ankle Mobility",
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


def dedupe_name_key(name: str) -> str:
    """Canonical key for routine duplicate detection (spec keys + aliases)."""
    return spec_key_for_name(name) or normalize_exercise_name(name)


def is_teen_only_exercise(exercise) -> bool:
    """True for HGH teen exclusives (flag or known spec/name)."""
    if getattr(exercise, "teen_only", False):
        return True
    key = spec_key_for_name(getattr(exercise, "name", "") or "")
    return bool(key and key in TEEN_ONLY_HGH_NAMES)


def primary_secondary_for_exercise(exercise_or_name) -> tuple[str | None, str | None]:
    """Return Monday spec primary/secondary posture pillars for an exercise."""
    name = exercise_or_name if isinstance(exercise_or_name, str) else getattr(exercise_or_name, "name", "")
    key = spec_key_for_name(name)
    if key and key in SPEC_PRIMARY_SECONDARY:
        return SPEC_PRIMARY_SECONDARY[key]
    return None, None


def spec_points_for_exercise(exercise) -> int:
    """Spec point value, falling back to the DB value for unknown exercises."""
    key = spec_key_for_name(getattr(exercise, "name", "") or "")
    if key and key in EXERCISE_ASSIGNMENT_SPEC:
        return int(EXERCISE_ASSIGNMENT_SPEC[key].get("points") or getattr(exercise, "points", 0) or 0)
    return int(getattr(exercise, "points", 0) or 0)


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

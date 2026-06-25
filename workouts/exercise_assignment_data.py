"""
Exercise Assignment Spec — canonical metadata for the real 29-exercise catalog
(workoutassignments.md + EXERCISE_SPEC_SHEET.md). Phantom exercises are excluded
from assignment pools.
"""

def _pillar_pcts(primary: str, secondary: str) -> dict[str, int]:
    pcts = {"spinal_pct": 0, "collapse_pct": 0, "pelvic_pct": 0, "legs_pct": 0}
    field = {
        "spinal": "spinal_pct",
        "collapse": "collapse_pct",
        "pelvic": "pelvic_pct",
        "legs": "legs_pct",
    }
    pcts[field[primary]] = 70
    pcts[field[secondary]] = 30
    return pcts


TEEN_ONLY_HGH_NAMES = frozenset({
    "box jumps / jump squats",
    "box jumps",
    "hgh boost (sprint & burpees)",
    "hgh boost",
    "high knees",
    "jump rope",
    "lunges",
    "mountain climbers",
    "bodyweight squats",
    "squats",
})

# canonical_key -> spec row (real catalog only)
EXERCISE_ASSIGNMENT_SPEC: dict[str, dict] = {
    # ── Posture (21) ──
    "decompression hang": {
        "name": "Decompression Hang",
        "age_group": "both",
        **_pillar_pcts("spinal", "collapse"),
        "potency": 10, "hgh_score": 2, "beast_bonus": 3, "teen_only": False,
        "category": "posture", "points": 9,
    },
    "cobra stretch": {
        "name": "Cobra Stretch",
        "age_group": "both",
        **_pillar_pcts("spinal", "collapse"),
        "potency": 8, "hgh_score": 1, "beast_bonus": 1, "teen_only": False,
        "category": "posture", "points": 7,
    },
    "cat-cow stretch": {
        "name": "Cat-Cow Stretch",
        "age_group": "both",
        **_pillar_pcts("spinal", "collapse"),
        "potency": 6, "hgh_score": 1, "beast_bonus": 1, "teen_only": False,
        "category": "posture", "points": 6,
    },
    "child's pose with arm walks": {
        "name": "child's Pose with Arm Walks",
        "age_group": "both",
        **_pillar_pcts("spinal", "collapse"),
        "potency": 6, "hgh_score": 1, "beast_bonus": 0, "teen_only": False,
        "category": "posture", "points": 6,
    },
    "child's pose": {
        "name": "Child's Pose",
        "age_group": "both",
        **_pillar_pcts("spinal", "collapse"),
        "potency": 6, "hgh_score": 1, "beast_bonus": 0, "teen_only": False,
        "category": "posture", "points": 6,
    },
    "spinal twist stretch": {
        "name": "Spinal Twist Stretch",
        "age_group": "both",
        **_pillar_pcts("spinal", "pelvic"),
        "potency": 6, "hgh_score": 1, "beast_bonus": 1, "teen_only": False,
        "category": "posture", "points": 6,
    },
    "seated forward fold": {
        "name": "Seated Forward Fold",
        "age_group": "both",
        **_pillar_pcts("spinal", "legs"),
        "potency": 8, "hgh_score": 1, "beast_bonus": 1, "teen_only": False,
        "category": "posture", "points": 8,
    },
    "wall angels": {
        "name": "Wall Angels",
        "age_group": "both",
        **_pillar_pcts("collapse", "spinal"),
        "potency": 9, "hgh_score": 1, "beast_bonus": 2, "teen_only": False,
        "category": "posture", "points": 7,
    },
    "doorway chest stretch": {
        "name": "Doorway Chest Stretch",
        "age_group": "both",
        **_pillar_pcts("collapse", "spinal"),
        "potency": 8, "hgh_score": 1, "beast_bonus": 1, "teen_only": False,
        "category": "posture", "points": 6,
    },
    "chin tucks": {
        "name": "Chin Tucks",
        "age_group": "both",
        **_pillar_pcts("collapse", "spinal"),
        "potency": 6, "hgh_score": 1, "beast_bonus": 0, "teen_only": False,
        "category": "posture", "points": 5,
    },
    "superman hold": {
        "name": "Superman Hold",
        "age_group": "both",
        **_pillar_pcts("collapse", "spinal"),
        "potency": 7, "hgh_score": 4, "beast_bonus": 2, "teen_only": False,
        "category": "posture", "points": 7,
    },
    "tadasana (mountain pose)": {
        "name": "Tadasana (Mountain Pose)",
        "age_group": "both",
        **_pillar_pcts("collapse", "spinal"),
        "potency": 5, "hgh_score": 1, "beast_bonus": 0, "teen_only": False,
        "category": "posture", "points": 6,
    },
    "foam roller thoracic extension": {
        "name": "Foam Roller Thoracic Extension",
        "age_group": "both",
        **_pillar_pcts("collapse", "spinal"),
        "potency": 9, "hgh_score": 1, "beast_bonus": 2, "teen_only": False,
        "category": "posture", "points": 9,
    },
    "glute bridges": {
        "name": "Glute Bridges",
        "age_group": "both",
        **_pillar_pcts("pelvic", "legs"),
        "potency": 8, "hgh_score": 3, "beast_bonus": 2, "teen_only": False,
        "category": "posture", "points": 7,
    },
    "hip flexor stretch": {
        "name": "Hip Flexor Stretch",
        "age_group": "both",
        **_pillar_pcts("pelvic", "legs"),
        "potency": 9, "hgh_score": 1, "beast_bonus": 1, "teen_only": False,
        "category": "posture", "points": 7,
    },
    "pelvic tilts": {
        "name": "Pelvic Tilts",
        "age_group": "both",
        **_pillar_pcts("pelvic", "spinal"),
        "potency": 6, "hgh_score": 1, "beast_bonus": 0, "teen_only": False,
        "category": "posture", "points": 6,
    },
    "plank": {
        "name": "Plank",
        "age_group": "both",
        **_pillar_pcts("pelvic", "spinal"),
        "potency": 7, "hgh_score": 5, "beast_bonus": 3, "teen_only": False,
        "category": "posture", "points": 7,
    },
    "bird-dog": {
        "name": "Bird-Dog",
        "age_group": "both",
        **_pillar_pcts("pelvic", "spinal"),
        "potency": 5, "hgh_score": 1, "beast_bonus": 0, "teen_only": False,
        "category": "posture", "points": 5,
    },
    "hamstring stretch": {
        "name": "Hamstring Stretch",
        "age_group": "both",
        **_pillar_pcts("legs", "pelvic"),
        "potency": 7, "hgh_score": 1, "beast_bonus": 0, "teen_only": False,
        "category": "posture", "points": 6,
    },
    "butterfly stretch": {
        "name": "Butterfly Stretch",
        "age_group": "both",
        **_pillar_pcts("legs", "pelvic"),
        "potency": 5, "hgh_score": 1, "beast_bonus": 0, "teen_only": False,
        "category": "posture", "points": 5,
    },
    "deep squat hold": {
        "name": "Deep Squat Hold",
        "age_group": "both",
        **_pillar_pcts("legs", "pelvic"),
        "potency": 8, "hgh_score": 2, "beast_bonus": 1, "teen_only": False,
        "category": "posture", "points": 8,
    },
    # ── HGH (8) — teen only ──
    "jump rope": {
        "name": "Jump Rope",
        "age_group": "teen",
        "spinal_pct": 15, "collapse_pct": 10, "pelvic_pct": 20, "legs_pct": 55,
        "potency": 6, "hgh_score": 9, "beast_bonus": 2, "teen_only": True,
        "category": "hgh", "points": 9,
    },
    "box jumps / jump squats": {
        "name": "Box Jumps / Jump Squats",
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
    "bodyweight squats": {
        "name": "Bodyweight Squats",
        "age_group": "teen",
        "spinal_pct": 5, "collapse_pct": 5, "pelvic_pct": 35, "legs_pct": 55,
        "potency": 7, "hgh_score": 8, "beast_bonus": 1, "teen_only": True,
        "category": "hgh", "points": 8,
    },
    "squats": {
        "name": "Squats",
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
    "hgh boost (sprint & burpees)": {
        "name": "HGH Boost (Sprint & Burpees)",
        "age_group": "teen",
        "spinal_pct": 10, "collapse_pct": 10, "pelvic_pct": 30, "legs_pct": 50,
        "potency": 8, "hgh_score": 10, "beast_bonus": 3, "teen_only": True,
        "category": "hgh", "points": 15,
    },
}

REAL_CATALOG_SPEC_KEYS = frozenset(EXERCISE_ASSIGNMENT_SPEC.keys())

# DB name aliases -> canonical spec key
EXERCISE_NAME_ALIASES = {
    "hanging from bar": "decompression hang",
    "hanging form bar": "decompression hang",
    "hanging": "decompression hang",
    "box jumps": "box jumps / jump squats",
    "jump squats": "box jumps / jump squats",
    "child's pose w/ arm walks": "child's pose with arm walks",
    "child's pose with arm walks": "child's pose with arm walks",
    "tadasana / mountain": "tadasana (mountain pose)",
    "cat-cow": "cat-cow stretch",
    "doorways chest stretch": "doorway chest stretch",
    "mountain climber": "mountain climbers",
    "bird dog": "bird-dog",
    "posterior pelvic tilt (pelvic tilts)": "pelvic tilts",
    "posterior pelvic tilt": "pelvic tilts",
    "hgh boost": "hgh boost (sprint & burpees)",
}

BEAST_MODE_CANONICAL_KEYS = frozenset()


def _primary_from_pcts(spec: dict) -> str:
    pairs = [
        ("spinal", spec.get("spinal_pct", 0) or 0),
        ("collapse", spec.get("collapse_pct", 0) or 0),
        ("pelvic", spec.get("pelvic_pct", 0) or 0),
        ("legs", spec.get("legs_pct", 0) or 0),
    ]
    return max(pairs, key=lambda item: item[1])[0]


def _secondary_from_pcts(spec: dict) -> str:
    pairs = sorted(
        [
            ("spinal", spec.get("spinal_pct", 0) or 0),
            ("collapse", spec.get("collapse_pct", 0) or 0),
            ("pelvic", spec.get("pelvic_pct", 0) or 0),
            ("legs", spec.get("legs_pct", 0) or 0),
        ],
        key=lambda item: item[1],
        reverse=True,
    )
    return pairs[1][0] if len(pairs) > 1 else pairs[0][0]


SPEC_PRIMARY_SECONDARY = {
    key: (_primary_from_pcts(spec), _secondary_from_pcts(spec))
    for key, spec in EXERCISE_ASSIGNMENT_SPEC.items()
    if spec.get("category") == "posture"
}


TEEN_CORE_BASE_NAMES = [
    "Jump Rope",
    "Decompression Hang",
    "Wall Angels",
    "Glute Bridges",
    "Hamstring Stretch",
]

TEEN_CORE_6_NAMES = TEEN_CORE_BASE_NAMES

# Master spec §3.1 — Core 6 by age bracket (adults 21+).
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
        "Doorway Chest Stretch",
        "Hip Flexor Stretch",
        "Butterfly Stretch",
    ],
    60: [
        "Decompression Hang",
        "Cobra Stretch",
        "Wall Angels",
        "Doorway Chest Stretch",
        "Hip Flexor Stretch",
        "Butterfly Stretch",
    ],
}

ADULT_POSTURE_POOL_CANONICAL_NAMES = [
    EXERCISE_ASSIGNMENT_SPEC[k]["name"]
    for k in REAL_CATALOG_SPEC_KEYS
    if not EXERCISE_ASSIGNMENT_SPEC[k].get("teen_only")
]

TEEN_POSTURE_POOL_CANONICAL_NAMES = list(ADULT_POSTURE_POOL_CANONICAL_NAMES)

TEEN_HGH_POOL_CANONICAL_NAMES = [
    EXERCISE_ASSIGNMENT_SPEC[k]["name"]
    for k in REAL_CATALOG_SPEC_KEYS
    if EXERCISE_ASSIGNMENT_SPEC[k].get("teen_only")
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


def is_real_catalog_exercise(exercise_or_name) -> bool:
    name = exercise_or_name if isinstance(exercise_or_name, str) else getattr(exercise_or_name, "name", "")
    key = spec_key_for_name(name)
    return bool(key and key in REAL_CATALOG_SPEC_KEYS)


def is_teen_only_exercise(exercise) -> bool:
    """True for HGH teen exclusives (flag or known spec/name)."""
    if getattr(exercise, "teen_only", False):
        return True
    key = spec_key_for_name(getattr(exercise, "name", "") or "")
    return bool(key and key in TEEN_ONLY_HGH_NAMES)


def primary_secondary_for_exercise(exercise_or_name) -> tuple[str | None, str | None]:
    """Return primary/secondary posture pillars for an exercise."""
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

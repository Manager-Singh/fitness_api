"""Exercise Assignment Spec (Parts 1–2) — beast selection scores the full pool.

Historical note: an earlier model restricted Beast Mode to a 4-exercise posture
whitelist. The authoritative Exercise_Assignment_Spec.docx scores Beast across the
full remaining pool, so these tests assert the documented invariants instead:
  - adults never receive teen-only HGH moves (TC-N),
  - no exercise is assigned to more than one tier,
  - high-intensity non-whitelist moves (Plank, Superman Hold) can be beast.
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from utils.exercise_assignment import select_adult_recommended_beast
from workouts.exercise_assignment_data import (
    EXERCISE_ASSIGNMENT_SPEC,
    TEEN_ONLY_HGH_NAMES,
    dedupe_name_key,
    normalize_exercise_name,
)


def _ex_from_spec(key: str):
    spec = EXERCISE_ASSIGNMENT_SPEC[key]
    return SimpleNamespace(
        id=abs(hash(key)) % 1000000,
        name=spec["name"],
        teen_only=spec.get("teen_only", False),
        adult_only=spec.get("adult_only", False),
        spinal_pct=spec["spinal_pct"],
        collapse_pct=spec["collapse_pct"],
        pelvic_pct=spec["pelvic_pct"],
        legs_pct=spec["legs_pct"],
        potency=spec["potency"],
        hgh_score=spec["hgh_score"],
        beast_bonus=spec["beast_bonus"],
        assignment_matrix_ready=True,
    )


def _adult_pool():
    return [
        _ex_from_spec(k)
        for k, v in EXERCISE_ASSIGNMENT_SPEC.items()
        if not v.get("teen_only") and not v.get("adult_only")
    ]


class BeastSelectionFullPoolTests(SimpleTestCase):
    def test_adult_beast_can_be_non_whitelist_intense_move(self):
        # Collapse-dominant user. Recommended (no beast bonus) takes Doorway + Wall
        # Angels; beast (intensity weighted) should then surface Superman Hold / Plank.
        losses = {"spinal": 0.2, "collapse": 1.5, "pelvic": 0.3, "legs": 0.1}
        pool = _adult_pool()
        core = [_ex_from_spec("decompression hang"), _ex_from_spec("cobra stretch")]
        rec, beast = select_adult_recommended_beast(pool, losses, core)
        beast_names = {e.name for e in beast}
        self.assertEqual(len(beast), 2)
        # At least one classic non-whitelist intense move appears in beast.
        self.assertTrue(beast_names & {"Superman Hold", "Plank", "Butterfly Stretch"})

    def test_no_exercise_in_two_tiers(self):
        losses = {"spinal": 0.5, "collapse": 1.0, "pelvic": 0.8, "legs": 0.4}
        pool = _adult_pool()
        core = [_ex_from_spec("decompression hang"), _ex_from_spec("cobra stretch")]
        rec, beast = select_adult_recommended_beast(pool, losses, core)
        ids = [e.id for e in rec + beast]
        keys = [dedupe_name_key(e.name) for e in rec + beast]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(keys), len(set(keys)))
        core_ids = {e.id for e in core}
        self.assertFalse(core_ids & set(ids))

    def test_tc_n_adult_never_teen_only(self):
        import random

        pool = _adult_pool()
        core = [_ex_from_spec("decompression hang")]
        for _ in range(50):
            losses = {
                "spinal": random.random(),
                "collapse": random.random() * 2,
                "pelvic": random.random(),
                "legs": random.random(),
            }
            rec, beast = select_adult_recommended_beast(pool, losses, core)
            for ex in rec + beast:
                self.assertFalse(ex.teen_only)
                self.assertNotIn(normalize_exercise_name(ex.name), TEEN_ONLY_HGH_NAMES)

    def test_dedupe_logic_normalized_names(self):
        seen: set[str] = set()
        names = ["Doorway Chest Stretch", "Doorways Chest Stretch", "Wall Angels"]
        kept = []
        for name in names:
            key = dedupe_name_key(name)
            if key in seen:
                continue
            seen.add(key)
            kept.append(key)
        self.assertEqual(len(kept), 2)
        self.assertEqual(kept.count("doorway chest stretch"), 1)

from types import SimpleNamespace

from django.test import SimpleTestCase

from utils.exercise_assignment import (
    allocate_variable_slots,
    select_adult_recommended_beast,
    select_teen_recommended_beast,
)
from workouts.exercise_assignment_data import EXERCISE_ASSIGNMENT_SPEC


def _ex(key, id_num):
    spec = EXERCISE_ASSIGNMENT_SPEC[key]
    return SimpleNamespace(
        id=id_num,
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


class PostureTargetingAllocationTests(SimpleTestCase):
    def test_largest_remainder_slots_sum_to_four(self):
        core = [
            _ex("decompression hang", 1),
            _ex("wall angels", 2),
            _ex("glute bridges", 3),
            _ex("hamstring stretch", 4),
        ]
        losses = {"spinal": 0.8, "collapse": 2.5, "pelvic": 0.9, "legs": 0.3}
        slots = allocate_variable_slots(losses, core, count=4, share_pts=6.75)

        self.assertEqual(sum(slots.values()), 4)
        self.assertGreaterEqual(slots["collapse"], 1)

    def test_selection_excludes_hgh_and_fills_primary_pillar_pool(self):
        pool = [
            _ex("wall angels", 10),
            _ex("standing posture reset", 11),
            _ex("doorway chest stretch", 12),
            _ex("box jumps", 13),
            _ex("decompression hang", 14),
            _ex("glute bridges", 15),
            _ex("hamstring stretch", 16),
        ]
        core = [_ex("decompression hang", 20), _ex("glute bridges", 21), _ex("hamstring stretch", 22)]
        losses = {"spinal": 0.1, "collapse": 3.0, "pelvic": 0.2, "legs": 0.1}

        rec, beast = select_adult_recommended_beast(pool, losses, core)
        selected = rec + beast

        self.assertTrue(selected)
        self.assertTrue(all(not ex.teen_only for ex in selected))
        self.assertIn("Standing Posture Reset", {ex.name for ex in selected})

    def test_teen_13_to_18_gets_guaranteed_hgh_final_variable_slot(self):
        pool = [
            _ex("decompression hang", 10),
            _ex("standing posture reset", 11),
            _ex("doorway chest stretch", 12),
            _ex("glute bridges", 13),
            _ex("hamstring stretch", 14),
            _ex("box jumps", 15),
            _ex("high knees", 16),
        ]
        core = [_ex("jump rope", 20), _ex("wall angels", 21), _ex("glute bridges", 22)]
        losses = {"spinal": 2.0, "collapse": 1.0, "pelvic": 0.8, "legs": 0.4}

        rec, beast = select_teen_recommended_beast(pool, losses, 14, core)

        self.assertEqual(len(rec + beast), 4)
        self.assertTrue(beast[-1].teen_only)

    def test_all_optimized_teen_variable_slots_become_hgh(self):
        pool = [
            _ex("box jumps", 10),
            _ex("high knees", 11),
            _ex("mountain climbers", 12),
            _ex("lunges", 13),
            _ex("standing posture reset", 14),
        ]
        core = [_ex("jump rope", 20), _ex("wall angels", 21)]
        losses = {"spinal": 0, "collapse": 0, "pelvic": 0, "legs": 0}

        rec, beast = select_teen_recommended_beast(pool, losses, 14, core)

        self.assertEqual(len(rec + beast), 4)
        self.assertTrue(all(ex.teen_only for ex in rec + beast))

    def test_twenty_year_old_has_no_forced_hgh_variable_slot(self):
        pool = [
            _ex("decompression hang", 10),
            _ex("standing posture reset", 11),
            _ex("doorway chest stretch", 12),
            _ex("glute bridges", 13),
            _ex("hamstring stretch", 14),
            _ex("box jumps", 15),
        ]
        core = [_ex("jump rope", 20), _ex("wall angels", 21), _ex("glute bridges", 22)]
        losses = {"spinal": 2.0, "collapse": 1.0, "pelvic": 0.8, "legs": 0.4}

        rec, beast = select_teen_recommended_beast(pool, losses, 20, core)

        self.assertTrue(rec + beast)
        self.assertTrue(all(not ex.teen_only for ex in rec + beast))

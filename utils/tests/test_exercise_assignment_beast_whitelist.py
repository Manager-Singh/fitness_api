"""Section 10.2 — beast tier whitelist and duplicate prevention."""
from types import SimpleNamespace

from django.test import SimpleTestCase

from utils.exercise_assignment import (
    _is_beast_mode_eligible,
    select_adult_recommended_beast,
)
from workouts.exercise_assignment_data import dedupe_name_key, normalize_exercise_name


def _ex(name, **kwargs):
    defaults = {
        "teen_only": False,
        "spinal_pct": 50,
        "collapse_pct": 50,
        "pelvic_pct": 50,
        "legs_pct": 50,
        "potency": 7,
        "hgh_score": 1,
        "beast_bonus": 1,
        "assignment_matrix_ready": True,
    }
    defaults.update(kwargs)
    return SimpleNamespace(id=hash(name) % 100000, name=name, **defaults)


class BeastWhitelistTests(SimpleTestCase):
    def test_doorway_not_beast_eligible(self):
        doorway = _ex("Doorway Chest Stretch")
        self.assertFalse(_is_beast_mode_eligible(doorway))
        self.assertTrue(_is_beast_mode_eligible(_ex("Wall Angels")))

    def test_beast_picks_only_whitelist(self):
        pool = [
            _ex("Doorway Chest Stretch"),
            _ex("Doorways Chest Stretch"),
            _ex("Wall Angels"),
            _ex("Glute Bridges"),
            _ex("Hip Flexor Stretch"),
            _ex("Decompression Hang"),
            _ex("Cat-Cow Stretch"),
        ]
        core = [_ex("Cobra Stretch"), _ex("Hamstring Stretch")]
        losses = {"spinal": 0.5, "collapse": 1.0, "pelvic": 0.8, "legs": 0.4}
        rec, beast = select_adult_recommended_beast(pool, losses, core)
        for ex in beast:
            key = normalize_exercise_name(ex.name)
            self.assertIn(
                key,
                {"decompression hang", "wall angels", "glute bridges", "hip flexor stretch"},
            )
            self.assertNotEqual(key, "doorway chest stretch")

    def test_beast_filled_when_all_whitelist_in_core(self):
        """Adult core 6 often includes all four beast whitelist moves; still assign 2 beast."""
        core = [
            _ex("Decompression Hang"),
            _ex("Cobra Stretch"),
            _ex("Glute Bridges"),
            _ex("Hip Flexor Stretch"),
            _ex("Pelvic Tilts"),
            _ex("Wall Angels"),
        ]
        pool = core + [
            _ex("Hamstring Stretch"),
            _ex("Butterfly Stretch"),
            _ex("Doorway Chest Stretch"),
        ]
        losses = {"spinal": 0.5, "collapse": 1.0, "pelvic": 0.8, "legs": 0.4}
        rec, beast = select_adult_recommended_beast(pool, losses, core)
        self.assertEqual(len(beast), 2)
        for ex in beast:
            self.assertTrue(_is_beast_mode_eligible(ex))

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

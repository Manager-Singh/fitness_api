from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

from utils.exercise_assignment import (
    get_age_multipliers,
    ranked_segments_from_losses,
    score_adult_exercise,
    score_teen_beast,
    score_teen_recommended,
    segment_losses_from_breakdown,
    select_adult_recommended_beast,
    select_teen_recommended_beast,
)
from utils.routine_genrate import build_posture_routine_slots
from workouts.exercise_assignment_data import (
    ADULT_CORE_6_BY_MIN_AGE,
    EXERCISE_ASSIGNMENT_SPEC,
    TEEN_ONLY_HGH_NAMES,
    apply_spec_to_exercise_dict,
    primary_secondary_for_exercise,
)
from workouts.models import AgeBracket, Exercise, RoutineTemplate, RoutineVariant, Tier, Track, Unit, VariantExercise


def _ex_from_spec(key: str):
    spec = EXERCISE_ASSIGNMENT_SPEC[key]
    row = SimpleNamespace(
        id=hash(key) % 100000,
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
    return row


def _adult_pool():
    return [
        _ex_from_spec(k)
        for k, v in EXERCISE_ASSIGNMENT_SPEC.items()
        if not v.get("teen_only") and not v.get("adult_only")
    ]


def _teen_pool():
    return [_ex_from_spec(k) for k in EXERCISE_ASSIGNMENT_SPEC.keys()]


class ExerciseAssignmentScoringTests(SimpleTestCase):
    def test_segment_losses_from_issue9_contract(self):
        contract = {
            "mode": "issue9_visual",
            "segments": {
                "spinal": {"loss_cm": 0.2},
                "collapse": {"loss_cm": 1.5},
                "pelvic": {"loss_cm": 0.3},
                "legs": {"loss_cm": 0.1},
            },
        }
        losses = segment_losses_from_breakdown({}, contract)
        self.assertEqual(losses["collapse"], 1.5)

    def test_tc_a2_collapse_dominant_recommended(self):
        losses = {"spinal": 0.2, "collapse": 1.5, "pelvic": 0.3, "legs": 0.1}
        pool = _adult_pool()
        core = [_ex_from_spec("decompression hang"), _ex_from_spec("cobra stretch")]
        rec, beast = select_adult_recommended_beast(pool, losses, core)
        rec_names = {e.name for e in rec}
        self.assertTrue(
            rec_names
            & {"Doorway Chest Stretch", "Wall Angels", "Foam Roller Thoracic Extension", "Chin Tucks"}
        )
        self.assertIn("Wall Angels", rec_names)

    def test_tc_a1_low_losses_high_potency(self):
        losses = {"spinal": 0.05, "collapse": 0.05, "pelvic": 0.05, "legs": 0.05}
        pool = _adult_pool()
        core = [_ex_from_spec("chin tucks")] * 1
        rec, beast = select_adult_recommended_beast(pool, losses, core)
        names = {e.name for e in rec + beast}
        self.assertTrue(names & {"Decompression Hang", "Wall Angels", "Hip Flexor Stretch"})

    def test_tc_t1_teen_extra_slots_target_posture_pillars(self):
        """Monday spec: teen Rec/Beast posture slots target deficiencies, not HGH."""
        losses = {"spinal": 0.2, "collapse": 1.5, "pelvic": 0.3, "legs": 0.1}
        pool = _teen_pool()
        core = [_ex_from_spec(n) for n in ["decompression hang", "cobra stretch", "hip flexor stretch", "wall angels"]]
        _, beast = select_teen_recommended_beast(pool, losses, 13, core)
        posture_beast = [ex for ex in beast if not ex.teen_only]
        self.assertGreaterEqual(len(posture_beast), 1)

    def test_tc_t2_teen_beast_uses_posture_pool(self):
        losses = {"spinal": 0.2, "collapse": 1.5, "pelvic": 0.3, "legs": 0.1}
        pool = _teen_pool()
        core = [_ex_from_spec("decompression hang")]
        _, beast = select_teen_recommended_beast(pool, losses, 19, core)
        for ex in beast:
            self.assertFalse(ex.teen_only)

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
                self.assertNotIn(ex.name.lower(), TEEN_ONLY_HGH_NAMES)


class ExerciseAssignmentBackfillTests(TestCase):
    def test_backfilled_exercise_has_matrix(self):
        ex = Exercise.objects.filter(name__iexact="High Knees").first()
        if not ex:
            self.skipTest("High Knees not in DB")
        self.assertTrue(ex.teen_only)
        self.assertEqual(ex.spinal_pct + ex.collapse_pct + ex.pelvic_pct + ex.legs_pct, 100)

    def test_decompression_or_hang_alias(self):
        ex = (
            Exercise.objects.filter(name__iexact="Decompression Hang").first()
            or Exercise.objects.filter(name__iexact="Hanging from Bar").first()
        )
        self.assertIsNotNone(ex)
        self.assertIsNotNone(ex.potency)


class TuesdayAdultRoutineCoreTests(TestCase):
    def setUp(self):
        for spec in EXERCISE_ASSIGNMENT_SPEC.values():
            Exercise.objects.update_or_create(
                name=spec["name"],
                defaults={
                    **apply_spec_to_exercise_dict(spec),
                    "category": spec.get("category", "posture"),
                    "points": spec.get("points", 0),
                },
            )
        bracket, _ = AgeBracket.objects.update_or_create(
            min_age=40,
            max_age=49,
            defaults={"title": "40-49"},
        )
        template, _ = RoutineTemplate.objects.update_or_create(
            name="Tuesday stale variant regression",
            defaults={"notes": ""},
        )
        self.variant, _ = RoutineVariant.objects.update_or_create(
            template=template,
            age_bracket=bracket,
            track=Track.POSTURE,
            defaults={"notes": ""},
        )
        stale_core_names = [
            "Glute Bridges",
            "Hip Flexor Stretch",
            "Pelvic Tilts",
            "Bird-Dog",
            "Dead Bug",
            "Side Plank",
        ]
        for order, name in enumerate(stale_core_names, start=1):
            ex = Exercise.objects.get(name=name)
            VariantExercise.objects.update_or_create(
                variant=self.variant,
                exercise=ex,
                defaults={
                    "order": order,
                    "sets": 1,
                    "quantity_min": 30,
                    "unit": Unit.SECS,
                    "tier": Tier.CORE,
                },
            )

    def test_adult_core_ignores_stale_variant_core_rows(self):
        breakdown = {
            "spinal_compression": {"current_loss_cm": 0.4},
            "posture_collapse": {"current_loss_cm": 0.4},
            "pelvic_tilt_back": {"current_loss_cm": 0.4},
            "leg_hamstring": {"current_loss_cm": 2.0},
        }
        slots, _ = build_posture_routine_slots(
            self.variant,
            40,
            breakdown,
            is_teen_user=False,
        )
        core_names = [slot.exercise.name for slot, tier in slots if tier == Tier.CORE]
        self.assertEqual(core_names, ADULT_CORE_6_BY_MIN_AGE[40])

    def test_teen_spinal_worst_generates_spinal_heavy_plan(self):
        breakdown = {
            "spinal_compression": {"current_loss_cm": 2.5},
            "posture_collapse": {"current_loss_cm": 0.1},
            "pelvic_tilt_back": {"current_loss_cm": 0.1},
            "leg_hamstring": {"current_loss_cm": 0.1},
        }
        slots, _ = build_posture_routine_slots(
            self.variant,
            14,
            breakdown,
            is_teen_user=True,
        )
        primary_counts = {"spinal": 0, "collapse": 0, "pelvic": 0, "legs": 0}
        for slot, _tier in slots:
            primary, _secondary = primary_secondary_for_exercise(slot.exercise)
            if primary in primary_counts:
                primary_counts[primary] += 1

        core_names = [slot.exercise.name for slot, tier in slots if tier == Tier.CORE]
        self.assertIn("Jump Rope", core_names)
        self.assertGreaterEqual(primary_counts["spinal"], 3)
        self.assertGreater(primary_counts["spinal"], primary_counts["collapse"])
        self.assertGreater(primary_counts["spinal"], primary_counts["pelvic"])

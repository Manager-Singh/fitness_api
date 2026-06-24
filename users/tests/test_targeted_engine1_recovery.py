from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from users.models import PostureState
from nutration.models import AgeGroup, Food, Module
from nutration.models_log import NutraEntry, NutraSession
from users.spec_runtime import compute_targeted_engine1_recovery, set_daily_validated
from workouts.models import (
    Exercise,
    ExerciseCategory,
    RoutineType,
    Tier,
    Unit,
    UserRoutine,
    UserRoutineExercise,
    WorkoutEntry,
    WorkoutSession,
)


class TargetedEngine1RecoveryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="targeted_user",
            email="targeted@example.com",
            password="testpass123",
        )
        profile = self.user.profile
        profile.gender = "male"
        profile.current_height_cm = "175"
        profile.base_height_cm = "175"
        profile.save()
        self.state, _ = PostureState.objects.get_or_create(user=self.user)
        self.state.spinal_current_loss_um = 25000
        self.state.collapse_current_loss_um = 30000
        self.state.pelvic_current_loss_um = 15000
        self.state.legs_current_loss_um = 10000
        self.state.total_recoverable_loss_um = 80000
        self.state.questionnaire_completed = True
        self.state.save()
        self.log_date = date(2026, 6, 22)
        self.routine = UserRoutine.objects.create(user=self.user, routine_type=RoutineType.POSTURE)
        self.session = WorkoutSession.objects.create(user=self.user, user_routine=self.routine, date=self.log_date)

    def _exercise(self, name, points):
        ex, _ = Exercise.objects.update_or_create(
            name=name,
            defaults={
                "points": points,
                "category": ExerciseCategory.POSTURE,
                "spinal_pct": 100,
                "collapse_pct": 0,
                "pelvic_pct": 0,
                "legs_pct": 0,
                "potency": 5,
            },
        )
        return ex

    def test_spine_only_workout_only_credits_spine_and_secondary(self):
        ex = self._exercise("Decompression Hang", 9)
        WorkoutEntry.objects.create(session=self.session, exercise=ex, points=9)

        result = compute_targeted_engine1_recovery(
            self.user,
            self.log_date,
            age=25,
            state=self.state,
            adult_nutrition_points=15,
            habit_points=12,
        )

        shares = result["engine1_segment_shares_um"]
        self.assertGreater(shares["spinal"], 0)
        self.assertGreater(shares["collapse"], 0)
        self.assertEqual(shares["pelvic"], 0)
        self.assertEqual(shares["legs"], 0)
        self.assertEqual(result["trained_primary_pillars"], ["spinal"])
        self.assertEqual(set(result["forfeited_share_pillars"]), {"collapse", "pelvic", "legs"})

    def test_no_workout_forfeits_nutrition_and_habit_recovery(self):
        result = compute_targeted_engine1_recovery(
            self.user,
            self.log_date,
            age=25,
            state=self.state,
            adult_nutrition_points=15,
            habit_points=12,
        )

        self.assertEqual(result["engine1_delta_um"], 0)
        self.assertFalse(result["workouts_done_today"])

    def test_legs_only_workout_collects_only_legs_strict_share(self):
        ex = self._exercise("Hamstring Stretch", 8)
        WorkoutEntry.objects.create(session=self.session, exercise=ex, points=8)

        result = compute_targeted_engine1_recovery(
            self.user,
            self.log_date,
            age=25,
            state=self.state,
            adult_nutrition_points=16,
            habit_points=12,
        )

        strict = result["strict_share_segment_shares_um"]
        self.assertEqual(strict["spinal"], 0)
        self.assertEqual(strict["collapse"], 0)
        self.assertEqual(strict["pelvic"], 0)
        self.assertGreater(strict["legs"], 0)
        self.assertEqual(result["trained_primary_pillars"], ["legs"])

    def test_single_legs_workout_stays_sub_one_percent_recovery(self):
        ex = self._exercise("Hamstring Stretch", 6)
        WorkoutEntry.objects.create(session=self.session, exercise=ex, points=6)

        result = compute_targeted_engine1_recovery(
            self.user,
            self.log_date,
            age=25,
            state=self.state,
            adult_nutrition_points=0,
            habit_points=0,
        )

        legs_um = result["engine1_segment_shares_um"]["legs"]
        legs_percent = (legs_um / float(self.state.legs_current_loss_um)) * 100.0
        self.assertEqual(legs_um, 42)
        self.assertAlmostEqual(legs_percent, 0.42, places=2)
        self.assertLess(legs_percent, 1.0)

    def test_full_core_pillars_collect_all_strict_shares(self):
        for name in [
            "Decompression Hang",
            "Standing Posture Reset",
            "Glute Bridges",
            "Hamstring Stretch",
        ]:
            ex = self._exercise(name, 8)
            WorkoutEntry.objects.create(session=self.session, exercise=ex, points=8)

        result = compute_targeted_engine1_recovery(
            self.user,
            self.log_date,
            age=25,
            state=self.state,
            adult_nutrition_points=16,
            habit_points=0,
        )

        strict = result["strict_share_segment_shares_um"]
        self.assertEqual(set(result["trained_primary_pillars"]), {"spinal", "collapse", "pelvic", "legs"})
        self.assertTrue(all(amount > 0 for amount in strict.values()))

    def test_hgh_exercise_does_not_credit_posture_pillars(self):
        ex, _ = Exercise.objects.update_or_create(
            name="Jump Rope",
            defaults={
                "points": 9,
                "category": ExerciseCategory.HGH,
                "teen_only": True,
                "spinal_pct": 0,
                "collapse_pct": 0,
                "pelvic_pct": 0,
                "legs_pct": 100,
                "potency": 5,
            },
        )
        WorkoutEntry.objects.create(session=self.session, exercise=ex, points=9)

        result = compute_targeted_engine1_recovery(
            self.user,
            self.log_date,
            age=15,
            state=self.state,
            adult_nutrition_points=0,
            habit_points=12,
        )

        self.assertEqual(result["engine1_delta_um"], 0)
        self.assertEqual(result["trained_primary_pillars"], [])

    def test_daily_validation_requires_all_assigned_core_exercises(self):
        profile = self.user.profile
        profile.birth_date = date(2011, 6, 22)
        profile.gender = "male"
        profile.save()
        ex1 = self._exercise("Core Validation Hang", 7)
        ex2 = self._exercise("Core Validation Wall Angels", 7)
        ure1 = UserRoutineExercise.objects.create(
            routine=self.routine,
            exercise=ex1,
            tier=Tier.CORE,
            order=1,
            sets=1,
            qty_min=1,
            unit=Unit.REPS,
        )
        UserRoutineExercise.objects.create(
            routine=self.routine,
            exercise=ex2,
            tier=Tier.CORE,
            order=2,
            sets=1,
            qty_min=1,
            unit=Unit.REPS,
        )
        WorkoutEntry.objects.create(
            session=self.session,
            exercise=ex1,
            user_routine_exercise=ure1,
            points=7,
        )
        age_group, _ = AgeGroup.objects.get_or_create(
            name="Teen Test",
            defaults={"min_age": 13, "max_age": 20},
        )
        module, _ = Module.objects.get_or_create(
            name="Teen Test Nutrition",
            age_group=age_group,
            defaults={"type": Module.NUTRITION, "nutrition_category": Module.NUTRITION_CATEGORY_TEEN},
        )
        food, _ = Food.objects.get_or_create(name="Teen Test Food")
        nutra_session, _ = NutraSession.objects.get_or_create(user=self.user, date=self.log_date)
        NutraEntry.objects.create(session=nutra_session, module=module, food=food, score=1)

        daily = set_daily_validated(self.user, self.log_date)

        self.assertFalse(daily.validated)

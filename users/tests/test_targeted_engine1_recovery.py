from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from users.models import PostureState
from users.spec_runtime import compute_targeted_engine1_recovery
from workouts.models import Exercise, ExerciseCategory, RoutineType, UserRoutine, WorkoutEntry, WorkoutSession


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

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from user_profile.models import UserProfile
from workouts.models import (
    Exercise,
    ExerciseCategory,
    RoutineType,
    Tier,
    Unit,
    UserRoutine,
    UserRoutineExercise,
    WorkoutEntry,
)


User = get_user_model()


class WorkoutLogIdempotencyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="workout_idempotent",
            email="workout_idempotent@test.example",
            password="secret123",
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.birth_date = date.today() - timedelta(days=int(365.2425 * 28))
        profile.base_height_cm = "175"
        profile.save()

        self.exercise = Exercise.objects.create(
            name="Idempotent Wall Angels",
            short_name="Wall Angels",
            points=7,
            category=ExerciseCategory.POSTURE,
            spinal_pct=30,
            collapse_pct=70,
            pelvic_pct=0,
            legs_pct=0,
            potency=7,
        )
        self.routine = UserRoutine.objects.create(
            user=self.user,
            routine_type=RoutineType.POSTURE,
            is_active=True,
        )
        self.routine_exercise = UserRoutineExercise.objects.create(
            routine=self.routine,
            exercise=self.exercise,
            tier=Tier.CORE,
            order=1,
            sets=2,
            qty_min=10,
            unit=Unit.REPS,
        )

        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @override_settings(ADULT_PAYWALL_DISABLED=True)
    @patch("workouts.views_log.build_dashboard_new_embed", return_value={"dashboard": {}})
    @patch("workouts.views_log.rebuild_ledger_from_date")
    @patch("workouts.views_log.apply_engine_routing")
    def test_same_assigned_workout_credits_once_per_local_day(
        self,
        mock_apply_engine_routing,
        mock_rebuild_ledger,
        _mock_dashboard,
    ):
        body = {
            "user_routine": self.routine.id,
            "exercise_id": self.exercise.id,
            "points": 7,
            "sets_done": 2,
            "reps_done": 10,
        }

        first = self.client.post("/api/workout-logs", body, format="json")
        second = self.client.post("/api/workout-logs", body, format="json")

        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertFalse(first.data.get("duplicate"))
        self.assertTrue(second.data.get("duplicate"))
        self.assertTrue(second.data.get("logged"))
        self.assertFalse(second.data.get("counts_toward_engine"))
        self.assertEqual(
            WorkoutEntry.objects.filter(
                session__user=self.user,
                user_routine_exercise=self.routine_exercise,
            ).count(),
            1,
        )
        self.assertEqual(first.data["entry"]["id"], second.data["entry"]["id"])
        self.assertEqual(first.data["total_workouts_today"], 1)
        self.assertEqual(second.data["total_workouts_today"], 1)
        mock_apply_engine_routing.assert_called_once()
        mock_rebuild_ledger.assert_called_once()

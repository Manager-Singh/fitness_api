from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient, APIRequestFactory

from user_profile.models import UserProfile
from users.models import DailyLog, HeightLedger
from users.spec_runtime import LEDGER_ENTRY_DAILY_COMPUTE
from utils.adult_dashboard_metrics import adult_daily_gains_cm_today
from workouts.models import (
    AgeBracket,
    Exercise,
    ExerciseCategory,
    RoutineTemplate,
    RoutineType,
    RoutineVariant,
    Tier,
    Track,
    Unit,
    UserRoutine,
    UserRoutineExercise,
    VariantExercise,
    WorkoutSetCompletion,
)
from workouts.serializers_user_routine import UserRoutineExerciseSerializer


User = get_user_model()


class PerSetWorkoutLoggingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="per_set_user",
            email="per_set_user@test.example",
            password="secret123",
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.birth_date = date.today() - timedelta(days=int(365.2425 * 28))
        profile.base_height_cm = "175"
        profile.save()

        self.exercise = Exercise.objects.create(
            name="Per Set Cobra",
            short_name="Cobra",
            points=7,
            category=ExerciseCategory.POSTURE,
            spinal_pct=70,
            collapse_pct=30,
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
            qty_min=30,
            unit=Unit.SECS,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @override_settings(ADULT_PAYWALL_DISABLED=True)
    @patch("workouts.views_log.build_dashboard_new_embed", return_value={"dashboard": {}})
    @patch("workouts.views_log.rebuild_ledger_from_date", return_value={})
    def test_set_completion_credits_once_and_tracks_partial_progress(self, _mock_rebuild, _mock_dashboard):
        body = {
            "user_routine": self.routine.id,
            "exercise_id": self.exercise.id,
            "set_index": 1,
            "duration_s": 30,
        }

        first = self.client.post("/api/workout-logs", body, format="json")
        duplicate = self.client.post("/api/workout-logs", body, format="json")
        second = self.client.post(
            "/api/workout-logs",
            {**body, "set_index": 2},
            format="json",
        )

        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(first.data["points_credited"], 3.5)
        self.assertEqual(first.data["completed_sets"], 1)
        self.assertFalse(first.data["exercise_completed"])

        self.assertEqual(duplicate.status_code, 200, duplicate.data)
        self.assertTrue(duplicate.data["duplicate"])
        self.assertEqual(duplicate.data["points_credited"], 0.0)

        self.assertEqual(second.status_code, 201, second.data)
        self.assertEqual(second.data["completed_sets"], 2)
        self.assertTrue(second.data["exercise_completed"])

        completions = WorkoutSetCompletion.objects.filter(
            user=self.user,
            user_routine_exercise=self.routine_exercise,
        )
        self.assertEqual(completions.count(), 2)
        self.assertEqual(sum((c.points_credited for c in completions), Decimal("0.0000")), Decimal("7.0000"))

    @override_settings(ADULT_PAYWALL_DISABLED=True)
    @patch("workouts.views_log.build_dashboard_new_embed", return_value={"dashboard": {}})
    @patch("workouts.views_log.rebuild_ledger_from_date", return_value={})
    def test_legacy_full_exercise_payload_creates_all_set_completions(self, _mock_rebuild, _mock_dashboard):
        response = self.client.post(
            "/api/workout-logs",
            {
                "user_routine": self.routine.id,
                "exercise_id": self.exercise.id,
                "points": 7,
                "sets_done": 2,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["completed_sets"], 2)
        self.assertTrue(response.data["exercise_completed"])
        self.assertEqual(
            WorkoutSetCompletion.objects.filter(
                user=self.user,
                user_routine_exercise=self.routine_exercise,
            ).count(),
            2,
        )


class DashboardDailyGainsTests(TestCase):
    def test_adult_daily_gains_reads_ledger_delta_not_dailylog_points(self):
        user = User.objects.create_user(
            username="daily_gains_user",
            email="daily_gains_user@test.example",
            password="secret123",
        )
        today = date.today()
        DailyLog.objects.create(user=user, log_date=today, engine1_points=28)
        HeightLedger.objects.create(
            user=user,
            log_date=today,
            entry_type=LEDGER_ENTRY_DAILY_COMPUTE,
            delta_um=122,
            cumulative_um=122,
            engine1_delta_um=122,
            metadata={"engine1_delta_um": 122},
        )

        self.assertEqual(adult_daily_gains_cm_today(user, today), 0.0122)


class UnilateralMetadataSerializerTests(TestCase):
    def test_routine_serializer_exposes_switch_side_contract(self):
        user = User.objects.create_user(
            username="unilateral_user",
            email="unilateral_user@test.example",
            password="secret123",
        )
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.gender = "male"
        profile.save()
        exercise = Exercise.objects.create(
            name="Serializer Hamstring Stretch",
            short_name="Hamstring",
            points=6,
            category=ExerciseCategory.POSTURE,
        )
        bracket = AgeBracket.objects.create(title="20-29", min_age=20, max_age=29)
        template = RoutineTemplate.objects.create(name="Unilateral Template")
        variant = RoutineVariant.objects.create(template=template, age_bracket=bracket, track=Track.POSTURE)
        ve = VariantExercise.objects.create(
            variant=variant,
            exercise=exercise,
            order=1,
            sets=2,
            quantity_min=30,
            unit=Unit.SECS,
            tier=Tier.CORE,
            notes="per leg",
            is_unilateral=True,
            unilateral_label="leg",
        )
        routine = UserRoutine.objects.create(user=user, routine_type=RoutineType.POSTURE, is_active=True)
        ure = UserRoutineExercise.objects.create(
            routine=routine,
            variant_exercise=ve,
            exercise=exercise,
            tier=Tier.CORE,
            order=1,
            sets=2,
            qty_min=30,
            unit=Unit.SECS,
        )
        request = APIRequestFactory().get("/")
        request.user = user

        data = UserRoutineExerciseSerializer(ure, context={"request": request}).data

        self.assertTrue(data["is_unilateral"])
        self.assertEqual(data["unilateral_label"], "leg")
        self.assertEqual(data["switch_prompt_text"], "SWITCH LEGS")
        self.assertEqual(data["switch_countdown_seconds"], 3)
        self.assertEqual(data["credit_unit"], "set")

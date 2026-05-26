from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework.test import APIClient

from user_profile.models import UserProfile
from users.models import HeightLedger, PostureState, User
from users.spec_runtime import rebuild_ledger_from_date
from utils.adult_dashboard_live import build_adult_dashboard_live_payload
from workouts.models import (
    Exercise,
    ExerciseCategory,
    RoutineType,
    UserRoutine,
    UserRoutineExercise,
)


@patch("utils.adult_dashboard_live.check_subscription_or_response")
class AdultDashboardLivePayloadTests(TestCase):
    def _mock_paid_adult_sub(self):
        return MagicMock(data={"is_paid": True, "is_trial": False, "trial_day": None})

    def _adult_user(self, years_old=28):
        u = User.objects.create_user(
            username=f"adultlive{years_old}",
            email=f"adultlive{years_old}@test.example",
            password="secret123",
        )
        log_date = date.today()
        dob = log_date - timedelta(days=int(365.2425 * years_old))
        prof, _ = UserProfile.objects.get_or_create(user=u)
        prof.birth_date = dob
        prof.gender = "male"
        prof.base_height_cm = "175"
        prof.current_height_cm = "175"
        prof.save()
        ps, _ = PostureState.objects.get_or_create(user=u)
        ps.scan_completed = True
        ps.questionnaire_completed = True
        ps.total_recoverable_loss_um = int(3.3 * 10000)
        ps.spinal_current_loss_um = int(1.2 * 10000)
        ps.collapse_current_loss_um = int(0.95 * 10000)
        ps.pelvic_current_loss_um = int(0.7 * 10000)
        ps.legs_current_loss_um = int(0.45 * 10000)
        ps.save()
        return u

    def test_payload_shape_and_segment_keys(self, mock_sub):
        mock_sub.side_effect = lambda user: self._mock_paid_adult_sub()
        user = self._adult_user()
        payload = build_adult_dashboard_live_payload(user)
        self.assertIsNotNone(payload)
        for key in (
            "today_daily_points",
            "today_posture_plus_gain_cm",
            "today_total_gain_cm",
            "current_height_cm",
            "total_recovered_cm",
            "segments",
        ):
            self.assertIn(key, payload)
        self.assertEqual(set(payload["segments"].keys()), {"spinal", "collapse", "pelvic", "legs"})
        for seg in payload["segments"].values():
            self.assertIn("loss_cm", seg)
            self.assertIn("opt_pct", seg)

    def test_teen_returns_none(self, mock_sub):
        mock_sub.side_effect = lambda user: self._mock_paid_adult_sub()
        u = User.objects.create_user(
            username="teenlive",
            email="teenlive@test.example",
            password="secret123",
        )
        prof, _ = UserProfile.objects.get_or_create(user=u)
        prof.birth_date = date.today() - timedelta(days=int(365.2425 * 15))
        prof.gender = "male"
        prof.save()
        self.assertIsNone(build_adult_dashboard_live_payload(u))

    def test_female_18_adult_returns_payload(self, mock_sub):
        mock_sub.side_effect = lambda user: self._mock_paid_adult_sub()
        u = User.objects.create_user(
            username="female18live",
            email="female18live@test.example",
            password="secret123",
            account_tier="adult",
        )
        prof, _ = UserProfile.objects.get_or_create(user=u)
        prof.birth_date = date.today() - timedelta(days=int(365.2425 * 18.9))
        prof.gender = "female"
        prof.base_height_cm = "163"
        prof.current_height_cm = "163"
        prof.save()
        payload = build_adult_dashboard_live_payload(u)
        self.assertIsNotNone(payload)
        self.assertIn("today_daily_points", payload)

    def test_male_18_teen_returns_none(self, mock_sub):
        mock_sub.side_effect = lambda user: self._mock_paid_adult_sub()
        u = User.objects.create_user(
            username="male18live",
            email="male18live@test.example",
            password="secret123",
        )
        prof, _ = UserProfile.objects.get_or_create(user=u)
        prof.birth_date = date.today() - timedelta(days=int(365.2425 * 18.5))
        prof.gender = "male"
        prof.save()
        self.assertIsNone(build_adult_dashboard_live_payload(u))

    def test_height_updates_after_ledger_rebuild(self, mock_sub):
        mock_sub.side_effect = lambda user: self._mock_paid_adult_sub()
        user = self._adult_user()
        log_date = date.today()

        before = build_adult_dashboard_live_payload(user, log_date)
        self.assertEqual(before["total_recovered_cm"], 0.0)
        self.assertEqual(before["current_height_cm"], 175.0)

        HeightLedger.objects.create(
            user=user,
            log_date=log_date,
            entry_type="daily_compute",
            delta_um=7000,
            cumulative_um=7000,
            engine1_delta_um=7000,
            bio_delta_um=0,
            engine2_delta_dm=0,
            algorithm_version="v1",
            metadata={"engine1_delta_um": 7000},
        )
        rebuild_ledger_from_date(user, log_date)

        after = build_adult_dashboard_live_payload(user, log_date)
        self.assertGreater(after["total_recovered_cm"], 0.0)
        self.assertGreater(after["current_height_cm"], 175.0)


@patch("workouts.views_log.build_dashboard_new_embed")
@patch("workouts.views_log.check_subscription_or_response")
@patch("utils.adult_dashboard_live.check_subscription_or_response")
class WorkoutLogLiveResponseTests(TestCase):
    def _mock_paid_adult_sub(self):
        return MagicMock(data={"is_paid": True, "is_trial": False, "trial_day": None})

    def test_post_workout_log_includes_dashboard_new(
        self, mock_live_sub, mock_view_sub, mock_dashboard_embed
    ):
        mock_live_sub.side_effect = lambda user: self._mock_paid_adult_sub()
        mock_view_sub.side_effect = lambda user: self._mock_paid_adult_sub()
        mock_dashboard_embed.return_value = {
            "message": "Dashboard retrieved successfully",
            "dashboard": {
                "variant": "adult",
                "live_metrics": {"height_cm": 175.007, "total_recovered_cm": 0.007},
                "posture_optimization": {"bars_percent": {}},
            },
        }

        user = User.objects.create_user(
            username="wlive",
            email="wlive@test.example",
            password="secret123",
        )
        log_date = date.today()
        dob = log_date - timedelta(days=int(365.2425 * 28))
        prof, _ = UserProfile.objects.get_or_create(user=user)
        prof.birth_date = dob
        prof.base_height_cm = "175"
        prof.save()
        ps, _ = PostureState.objects.get_or_create(user=user)
        ps.scan_completed = True
        ps.questionnaire_completed = True
        ps.total_recoverable_loss_um = int(2.0 * 10000)
        ps.spinal_current_loss_um = int(1.0 * 10000)
        ps.save()

        ex, _ = Exercise.objects.get_or_create(
            name="Adult Live Wall Angels",
            defaults={"short_name": "Wall", "points": 7, "category": ExerciseCategory.POSTURE},
        )
        routine = UserRoutine.objects.create(
            user=user,
            routine_type=RoutineType.POSTURE,
            is_active=True,
        )
        UserRoutineExercise.objects.create(routine=routine, exercise=ex, sort_order=1)

        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.post(
            "/api/workout-logs",
            {
                "user_routine": routine.id,
                "exercise_id": ex.id,
                "points": 7,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIn("dashboard_new", resp.data)
        dash = resp.data["dashboard_new"]
        self.assertIn("dashboard", dash)
        self.assertIn("message", dash)
        self.assertEqual(dash["dashboard"].get("variant"), "adult")
        self.assertIn("live_metrics", dash["dashboard"])
        self.assertIn("posture_optimization", dash["dashboard"])
        self.assertNotIn("dashboard_embed_error", dash)

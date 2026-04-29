"""
v3.4 backend: Genetic_Average on DailyLog from daily compute, and dashboard-new payload shape.

Covers:
- Section 5.1b fields persisted on DailyLog for teens (13–20) when compute_daily_height_for_user runs
- Genetic fields cleared (null) for adults on DailyLog
- DashboardNewResponseSerializer accepts genetic_average_cm, daily_genetic_average_gain_cm,
  exercises_done, total_exercises, habits_logged alongside existing keys.
"""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase

from user_profile.models import UserProfile
from users.models import DailyLog, PostureState, User
from users.spec_runtime import compute_daily_height_for_user
from utils.posture.teen_genetic_average import (
    compute_daily_genetic_average_gain_cm,
    compute_genetic_average_cm,
)

from posture_questions.serializers_dashboard import DashboardNewResponseSerializer


@patch("users.spec_runtime.check_subscription_or_response")
class DailyLogGeneticAverageIntegrationTests(TestCase):
    """compute_daily_height_for_user writes Section 5.1b fields to DailyLog for teens only."""

    def _mock_sub_teen_paid(self):
        return MagicMock(data={"trial_day": None, "is_paid": True, "is_trial": False})

    def _teen_with_parents(self, log_date: date, years_old: int = 15):
        u = User.objects.create_user(
            username=f"v34ga{years_old}",
            email=f"v34ga{years_old}@test.example",
            password="secret123",
        )
        try:
            dob = log_date.replace(year=log_date.year - years_old)
        except ValueError:
            dob = log_date - timedelta(days=int(365.2425 * years_old))
        prof, _ = UserProfile.objects.get_or_create(user=u)
        prof.birth_date = dob
        prof.gender = "male"
        prof.base_height_cm = "165"
        prof.current_height_cm = "165"
        prof.father_height_cm = "182"
        prof.mother_height_cm = "168"
        prof.save()
        ps, _ = PostureState.objects.get_or_create(user=u)
        ps.scan_completed = True
        ps.questionnaire_completed = True
        ps.save()
        # Ensure ORM-visible profile (birth_date) is loaded on user for age helpers used in daily compute.
        return User.objects.select_related("profile").get(pk=u.pk)

    def test_teen_dailylog_matches_genetic_average_helpers(self, mock_sub):
        mock_sub.side_effect = lambda user: self._mock_sub_teen_paid()
        log_date = date(2024, 9, 1)
        u = self._teen_with_parents(log_date, years_old=15)

        compute_daily_height_for_user(u, log_date=log_date, force_recompute=True)

        daily = DailyLog.objects.get(user=u, log_date=log_date)
        self.assertIsNotNone(daily.genetic_average_cm)
        self.assertIsNotNone(daily.daily_genetic_average_gain_cm)

        expected_ga = compute_genetic_average_cm(u, log_date)
        expected_gain = compute_daily_genetic_average_gain_cm(u, log_date)

        self.assertAlmostEqual(float(daily.genetic_average_cm), float(expected_ga), places=3)
        self.assertAlmostEqual(
            float(daily.daily_genetic_average_gain_cm),
            float(expected_gain),
            places=5,
        )
        self.assertGreater(float(daily.genetic_average_cm), 0.0)
        self.assertGreaterEqual(float(daily.daily_genetic_average_gain_cm), 0.0)

    def test_adult_dailylog_genetic_fields_null(self, mock_sub):
        mock_sub.side_effect = lambda user: self._mock_sub_teen_paid()
        log_date = date(2024, 9, 1)
        u = User.objects.create_user(
            username="v34adult",
            email="v34adult@test.example",
            password="secret123",
        )
        dob = log_date - timedelta(days=int(365.2425 * 28))
        prof, _ = UserProfile.objects.get_or_create(user=u)
        prof.birth_date = dob
        prof.gender = "male"
        prof.base_height_cm = "175"
        prof.current_height_cm = "175"
        prof.father_height_cm = "180"
        prof.mother_height_cm = "165"
        prof.save()
        ps, _ = PostureState.objects.get_or_create(user=u)
        ps.scan_completed = True
        ps.questionnaire_completed = True
        ps.save()
        u = User.objects.select_related("profile").get(pk=u.pk)

        compute_daily_height_for_user(u, log_date=log_date, force_recompute=True)

        daily = DailyLog.objects.get(user=u, log_date=log_date)
        self.assertIsNone(daily.genetic_average_cm)
        self.assertIsNone(daily.daily_genetic_average_gain_cm)

    def test_teen_questionnaire_unlock_sets_dashboard_scan_completed(self, mock_sub):
        """
        v3.3+ teen unlock rule: scan OR questionnaire completion.
        Dashboard should not show scan_completed=false after successful questionnaire submit.
        """
        mock_sub.side_effect = lambda user: self._mock_sub_teen_paid()
        log_date = date(2024, 9, 1)
        u = self._teen_with_parents(log_date, years_old=15)
        # Explicitly simulate: questionnaire done, scan NOT done.
        ps = PostureState.objects.get(user=u)
        ps.scan_completed = False
        ps.questionnaire_completed = True
        ps.save()

        # Avoid deep routine generation / ML dependencies in this contract test.
        from unittest.mock import patch

        from rest_framework.test import APIRequestFactory, force_authenticate
        from posture_questions.views import get_dashboard_new
        from utils.posture.height_constants import default_optimization_breakdown_pending_scan

        factory = APIRequestFactory()
        req = factory.get("/api/dashboard-new")
        force_authenticate(req, user=u)
        with patch(
            "posture_questions.views.RoutineService.ensure_active_routine",
            return_value=None,
        ), patch(
            "posture_questions.views.PostureAnalysisService.get_posture_analysis",
            return_value=({}, default_optimization_breakdown_pending_scan()),
        ), patch(
            "posture_questions.views.compute_optimized_height",
            return_value={"mph_height_cm": 170.0, "optimized_height_cm": 175.0},
        ):
            resp = get_dashboard_new(req)
        self.assertEqual(getattr(resp, "status_code", None), 200)
        dash = resp.data.get("dashboard") or {}
        scan = dash.get("scan") or {}
        self.assertTrue(bool(scan.get("scan_completed")))


class DashboardNewV34SerializerTests(SimpleTestCase):
    """Serializer accepts v3.4 dashboard fields (no HTTP — avoids full dashboard graph stack)."""

    def test_teen_payload_with_genetic_and_button_fields_validates(self):
        payload = {
            "message": "Dashboard retrieved successfully",
            "dashboard": {
                "variant": "teen",
                "genetic_average_cm": 172.3456,
                "daily_genetic_average_gain_cm": 0.006421,
                "calculation_mode": "live",
                "anomalies": [],
                "profile": {"user_id": 1, "username": "t"},
                "live_metrics": {
                    "base_height_cm": 165.0,
                    "genetic_blue_cm": 166.0,
                    "us_optimized_red_cm": 166.5,
                    "height_cm": 166.5,
                    "daily_gains_cm": 0.01,
                    "genetic_cumulative_cm": 1.0,
                    "postureplus_cumulative_cm": 0.5,
                },
                "target_metrics": {
                    "genetic_blue_cm": 180.0,
                    "us_optimized_red_cm": 182.0,
                    "unoptimized_cm": 170.0,
                    "true_optimized_green_cm": None,
                },
                "scan": {
                    "scan_completed": True,
                    "can_scan": True,
                    "scan_message": "",
                    "rescan_timer_days": 5,
                    "teen_scan_required": False,
                },
                "top_graph": {
                    "cards": [
                        {"key": "genetic_plus", "label": "Genetic +", "value_cm": 0.01},
                        {"key": "posture_plus", "label": "Posture+", "value_cm": 0.002},
                        {"key": "daily_gains", "label": "Daily Gains", "value_cm": 0.012},
                        {"key": "height", "label": "Height", "value_cm": 166.5},
                    ],
                    "teen_lines_cm": {
                        "genetic_blue": 180.0,
                        "us_optimized_red": 182.0,
                        "true_optimized_green": None,
                        "true_optimized_locked": True,
                    },
                    "adult_target_height_cm": None,
                },
                "routine_progress": {
                    "cta": "Continue Routine — 2 of 6",
                    "posture_exercises_fraction": "2/6",
                    "posture_exercises_done": 2,
                    "posture_exercises_total": 6,
                    "exercises_done": 2,
                    "total_exercises": 6,
                    "habits_logged": 3,
                    "posture_exercises_percent": 33,
                    "nutrition_percent": 50,
                    "teen_nutrition_dots": 2,
                    "teen_lifestyle_dots": 1,
                    "streak_days": 1,
                    "daily_points": 10,
                    "rank": 5,
                },
                "posture_optimization": {
                    "total_recoverable_loss_cm": 2.0,
                    "total_current_loss_cm": 1.0,
                    "bars_percent": {"spinal_compression": 50},
                    "raw_segments": {},
                },
                "ai_analysis": {},
                "chart_breakdown": None,
                "subscription": {},
                "trial_data": {
                    "is_teen": True,
                    "is_trial": False,
                    "trial_day": None,
                    "trial_start": None,
                    "trial_end": None,
                    "full_access_trial_active": False,
                    "full_access_trial_expired": False,
                },
                "important_data": {},
                "meta": {"screen_state": "home", "age_exact": 15.2},
            },
        }
        ser = DashboardNewResponseSerializer(data=payload)
        self.assertTrue(ser.is_valid(), ser.errors)
        data = ser.validated_data["dashboard"]
        self.assertEqual(data["genetic_average_cm"], 172.3456)
        self.assertEqual(data["daily_genetic_average_gain_cm"], 0.006421)
        rp = data["routine_progress"]
        self.assertEqual(rp["exercises_done"], 2)
        self.assertEqual(rp["total_exercises"], 6)
        self.assertEqual(rp["habits_logged"], 3)
        self.assertEqual(rp["posture_exercises_done"], 2)
        self.assertEqual(rp["posture_exercises_total"], 6)

    def test_adult_payload_null_genetic_validates(self):
        payload = {
            "message": "Dashboard retrieved successfully",
            "dashboard": {
                "variant": "adult",
                "genetic_average_cm": None,
                "daily_genetic_average_gain_cm": None,
                "scan": {
                    "scan_completed": True,
                    "can_scan": True,
                    "scan_message": "",
                    "rescan_timer_days": 3,
                    "teen_scan_required": False,
                },
                "top_graph": {
                    "cards": [
                        {"key": "base_height", "label": "Base Height", "value_cm": 170.0},
                        {"key": "total_recovered", "label": "Total Recovered", "value_cm": 1.0},
                        {"key": "daily_gains", "label": "Daily Gains", "value_cm": 0.02},
                        {"key": "height", "label": "Height", "value_cm": 171.0},
                    ],
                    "teen_lines_cm": None,
                    "adult_target_height_cm": 175.0,
                },
                "routine_progress": {
                    "cta": "Start Today's Routine",
                    "posture_exercises_fraction": "0/6",
                    "posture_exercises_done": 0,
                    "posture_exercises_total": 6,
                    "exercises_done": 0,
                    "total_exercises": 6,
                    "habits_logged": 0,
                    "posture_exercises_percent": 0,
                    "nutrition_percent": 0,
                    "teen_nutrition_dots": None,
                    "teen_lifestyle_dots": None,
                    "streak_days": 0,
                    "daily_points": 0,
                    "rank": None,
                },
                "posture_optimization": {
                    "total_recoverable_loss_cm": 5.0,
                    "total_current_loss_cm": 2.0,
                    "bars_percent": {},
                    "raw_segments": {},
                },
            },
        }
        ser = DashboardNewResponseSerializer(data=payload)
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertIsNone(ser.validated_data["dashboard"]["genetic_average_cm"])

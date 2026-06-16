"""Monday A2 — strict paywall logging gates."""
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from user_profile.models import UserProfile
from utils.monetization_gate import is_logging_locked, logging_locked_payload

User = get_user_model()
_UNPAID_SUB = {"is_paid": False, "is_trial": False, "trial_day": None}


class LoggingLockedHelperTests(TestCase):
    def _teen_user(self):
        u = User.objects.create_user(
            username="teen_log_gate",
            email="teen_log_gate@test.example",
            password="secret123",
        )
        prof, _ = UserProfile.objects.get_or_create(user=u)
        prof.birth_date = date.today() - timedelta(days=int(365.2425 * 15))
        prof.save()
        u.account_tier = "teen"
        u.save()
        return u

    def _adult_user(self):
        u = User.objects.create_user(
            username="adult_log_gate",
            email="adult_log_gate@test.example",
            password="secret123",
        )
        prof, _ = UserProfile.objects.get_or_create(user=u)
        prof.age = "25"
        prof.save()
        u.account_tier = "adult"
        u.save()
        return u

    @override_settings(TEEN_PAYWALL_DISABLED=False, ADULT_PAYWALL_DISABLED=False)
    @patch("utils.check_payment.check_subscription_or_response")
    def test_unpaid_teen_is_logging_locked(self, mock_sub):
        mock_sub.return_value = type("R", (), {"data": _UNPAID_SUB})()
        user = self._teen_user()
        self.assertTrue(is_logging_locked(user))
        payload = logging_locked_payload(user)
        self.assertIsNotNone(payload)
        self.assertTrue(payload.get("paywall_required"))
        self.assertEqual(payload.get("gate"), "subscription_required")

    @override_settings(TEEN_PAYWALL_DISABLED=False, ADULT_PAYWALL_DISABLED=False)
    @patch("utils.check_payment.check_subscription_or_response")
    def test_unpaid_adult_is_logging_locked(self, mock_sub):
        mock_sub.return_value = type("R", (), {"data": _UNPAID_SUB})()
        user = self._adult_user()
        self.assertTrue(is_logging_locked(user))

    @override_settings(TEEN_PAYWALL_DISABLED=True, ADULT_PAYWALL_DISABLED=False)
    def test_teen_qa_bypass_unlocks_logging(self):
        user = self._teen_user()
        self.assertFalse(is_logging_locked(user))

    @override_settings(TEEN_PAYWALL_DISABLED=False, ADULT_PAYWALL_DISABLED=True)
    def test_adult_qa_bypass_unlocks_logging(self):
        user = self._adult_user()
        self.assertFalse(is_logging_locked(user))


class HabitLogPaywallAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="teen_habit_403",
            email="teen_habit_403@test.example",
            password="secret123",
        )
        prof, _ = UserProfile.objects.get_or_create(user=self.user)
        prof.birth_date = date.today() - timedelta(days=int(365.2425 * 14))
        prof.save()
        self.user.account_tier = "teen"
        self.user.save()
        self.client.force_authenticate(user=self.user)

    @override_settings(TEEN_PAYWALL_DISABLED=False, ADULT_PAYWALL_DISABLED=False)
    @patch("utils.check_payment.check_subscription_or_response")
    def test_unpaid_teen_habit_log_returns_403(self, mock_sub):
        mock_sub.return_value = type("R", (), {"data": _UNPAID_SUB})()
        resp = self.client.post(
            "/api/habit-logs",
            {"habit_code": "morning_sunlight", "slot": "am"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(resp.data.get("paywall_required"))

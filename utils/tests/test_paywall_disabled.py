from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from user_profile.models import UserProfile
from utils.check_payment import _apply_paywall_disabled_flags, check_subscription_or_response
from utils.monetization_gate import compute_monetization_flags

User = get_user_model()


class PaywallDisabledFlagTests(TestCase):
    def _teen_user(self):
        u = User.objects.create_user(
            username="teen_pw",
            email="teen_pw@test.example",
            password="secret123",
        )
        prof, _ = UserProfile.objects.get_or_create(user=u)
        prof.birth_date = date.today() - timedelta(days=int(365.2425 * 15))
        prof.save()
        u.account_tier = "teen"
        u.trial_start = u.trial_start or date.today()
        u.save()
        return u

    def _adult_user(self):
        u = User.objects.create_user(
            username="adult_pw",
            email="adult_pw@test.example",
            password="secret123",
        )
        prof, _ = UserProfile.objects.get_or_create(user=u)
        prof.age = "25"
        prof.save()
        u.account_tier = "adult"
        u.save()
        return u

    @override_settings(TEEN_PAYWALL_DISABLED=True, ADULT_PAYWALL_DISABLED=False)
    def test_teen_subscription_reports_paid_when_flag_on(self):
        user = self._teen_user()
        data = check_subscription_or_response(user).data
        self.assertTrue(data.get("is_paid"))

    @override_settings(TEEN_PAYWALL_DISABLED=True)
    def test_teen_monetization_never_trial_expired_when_flag_on(self):
        flags = compute_monetization_flags(
            15,
            {"is_paid": False, "is_trial": False, "trial_day": 12},
            age_exact=15.0,
        )
        self.assertFalse(flags["full_access_trial_expired"])
        self.assertTrue(flags["teen_full_access"])
        self.assertTrue(flags["conversion_enabled"])

    @override_settings(ADULT_PAYWALL_DISABLED=True, TEEN_PAYWALL_DISABLED=False)
    def test_adult_subscription_reports_paid_when_flag_on(self):
        user = self._adult_user()
        data = check_subscription_or_response(user).data
        self.assertTrue(data.get("is_paid"))

    @override_settings(ADULT_PAYWALL_DISABLED=True)
    def test_adult_monetization_conversion_enabled_when_flag_on(self):
        flags = compute_monetization_flags(
            25,
            {"is_paid": False, "is_trial": False, "trial_day": None},
            age_exact=25.0,
        )
        self.assertTrue(flags["is_paid"])
        self.assertTrue(flags["conversion_enabled"])

    @override_settings(TEEN_PAYWALL_DISABLED=True)
    def test_apply_flags_chain_caps_trial_day(self):
        teen = self._teen_user()
        payload = {"is_paid": False, "trial_day": 10, "is_trial": False}
        out = _apply_paywall_disabled_flags(teen, payload)
        self.assertTrue(out["is_paid"])
        self.assertLessEqual(int(out["trial_day"]), 7)

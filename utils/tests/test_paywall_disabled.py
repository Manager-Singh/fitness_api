from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from user_profile.models import UserProfile
from utils.check_payment import _apply_paywall_disabled_flags, check_subscription_or_response
from utils.paywall_flags import effective_is_paid, qa_paid_bypass_for_user
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

    @override_settings(TEEN_PAYWALL_DISABLED=True, ADULT_PAYWALL_DISABLED=True)
    def test_effective_is_paid_bypass_for_both_tiers(self):
        teen = self._teen_user()
        adult = self._adult_user()
        self.assertTrue(qa_paid_bypass_for_user(teen))
        self.assertTrue(qa_paid_bypass_for_user(adult))
        self.assertTrue(effective_is_paid(teen, {"is_paid": False}))
        self.assertTrue(effective_is_paid(adult, {"is_paid": False}))

    def test_female_adult_18_plus_not_trial_with_stale_trial_dates(self):
        """Female 18+ is adult; legacy 13–20 trial window must not apply."""
        now = timezone.now()
        u = User.objects.create_user(
            username="female_adult_trial",
            email="female_adult_trial@test.example",
            password="secret123",
        )
        prof, _ = UserProfile.objects.get_or_create(user=u)
        prof.gender = "Female"
        prof.birth_date = date.today() - timedelta(days=int(365.2425 * 18.95))
        prof.save()
        u.account_tier = "adult"
        u.trial_start = now - timedelta(days=1)
        u.trial_end = now + timedelta(days=6)
        u.save()

        data = check_subscription_or_response(u).data
        self.assertFalse(data.get("is_trial"))
        self.assertNotEqual(data.get("plan"), "Trial")
        self.assertIsNone(data.get("trial_day"))

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from payment_packages.models import MonetizationSettings
from posture.views import _mark_scan_completed
from user_profile.models import UserProfile
from utils.check_payment import check_subscription_or_response
from utils.monetization_gate import compute_monetization_flags
from utils.trial_settings import teen_trial_globally_enabled

User = get_user_model()


@override_settings(TEEN_PAYWALL_DISABLED=False, ADULT_PAYWALL_DISABLED=False)
class TeenTrialAdminToggleTests(TestCase):
    def setUp(self):
        MonetizationSettings.objects.update_or_create(
            pk=1, defaults={"teen_trial_enabled": True}
        )

    def _teen_with_active_trial(self):
        user = User.objects.create_user(
            username="trial_teen",
            email="trial_teen@test.example",
            password="secret123",
        )
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.birth_date = date.today() - timedelta(days=int(365.2425 * 15))
        profile.gender = "male"
        profile.age = "15"
        profile.save()
        now = timezone.now()
        user.account_tier = "teen"
        user.trial_start = now - timedelta(days=1)
        user.trial_end = now + timedelta(days=6)
        user.save()
        return User.objects.get(pk=user.pk)

    def test_global_helper_reflects_admin_setting(self):
        MonetizationSettings.objects.filter(pk=1).update(teen_trial_enabled=True)
        from django.core.cache import cache

        cache.delete("monetization_teen_trial_enabled")
        self.assertTrue(teen_trial_globally_enabled())

        MonetizationSettings.objects.filter(pk=1).update(teen_trial_enabled=False)
        from django.core.cache import cache

        cache.delete("monetization_teen_trial_enabled")
        self.assertFalse(teen_trial_globally_enabled())

    def test_active_trial_not_honored_when_disabled(self):
        MonetizationSettings.objects.filter(pk=1).update(teen_trial_enabled=False)
        from django.core.cache import cache

        cache.delete("monetization_teen_trial_enabled")

        user = self._teen_with_active_trial()
        data = check_subscription_or_response(user).data
        self.assertFalse(data.get("is_trial"))
        self.assertFalse(data.get("teen_trial_enabled"))
        self.assertEqual(data.get("plan"), "Free")

    def test_active_trial_honored_when_enabled(self):
        MonetizationSettings.objects.filter(pk=1).update(teen_trial_enabled=True)
        from django.core.cache import cache

        cache.delete("monetization_teen_trial_enabled")

        user = self._teen_with_active_trial()
        data = check_subscription_or_response(user).data
        self.assertTrue(data.get("is_trial"))
        self.assertTrue(data.get("teen_trial_enabled"))
        self.assertEqual(data.get("plan"), "Trial")

    def test_scan_does_not_start_trial_when_disabled(self):
        MonetizationSettings.objects.filter(pk=1).update(teen_trial_enabled=False)
        from django.core.cache import cache

        cache.delete("monetization_teen_trial_enabled")

        user = User.objects.create_user(
            username="scan_teen",
            email="scan_teen@test.example",
            password="secret123",
        )
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.birth_date = date.today() - timedelta(days=int(365.2425 * 15))
        profile.gender = "male"
        profile.age = "15"
        profile.save()
        user.account_tier = "teen"
        user.save()
        _mark_scan_completed(user)
        user = User.objects.get(pk=user.pk)
        self.assertIsNone(user.trial_start)
        self.assertIsNone(user.trial_end)

    def test_monetization_flags_include_teen_trial_enabled(self):
        MonetizationSettings.objects.filter(pk=1).update(teen_trial_enabled=False)
        from django.core.cache import cache

        cache.delete("monetization_teen_trial_enabled")

        user = self._teen_with_active_trial()
        sub = check_subscription_or_response(user).data
        flags = compute_monetization_flags(15, sub, age_exact=15.0, user=user)
        self.assertFalse(flags.get("is_trial"))
        self.assertFalse(flags.get("teen_trial_enabled"))
        self.assertFalse(flags.get("teen_full_access"))

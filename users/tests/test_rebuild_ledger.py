"""Section 14.2 — rebuildLedgerFromDate and force_recompute."""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase

from user_profile.models import UserProfile
from users.models import DailyLog, HeightLedger, PostureState, User
from users.spec_runtime import compute_daily_height_for_user, rebuild_ledger_from_date


@patch("users.spec_runtime.check_subscription_or_response")
class RebuildLedgerTests(TestCase):
    def _teen_user(self):
        u = User.objects.create_user(
            username="rlteen",
            email="rlteen@test.example",
            password="secret123",
        )
        dob = date.today() - timedelta(days=int(365.2425 * 15))
        UserProfile.objects.create(
            user=u,
            birth_date=dob,
            gender="male",
            base_height_cm="160",
            current_height_cm="160",
        )
        ps, _ = PostureState.objects.get_or_create(user=u)
        ps.scan_completed = True
        ps.questionnaire_completed = True
        ps.save()
        return u

    def test_force_recompute_rewrites_same_day(self, mock_sub):
        mock_sub.return_value = MagicMock(
            data={"trial_day": None, "is_paid": True, "is_trial": False}
        )
        u = self._teen_user()
        d = date(2024, 6, 10)
        DailyLog.objects.create(
            user=u,
            log_date=d,
            exercise_points=0,
            food_points=0,
            lifestyle_points=0,
        )
        r1 = compute_daily_height_for_user(u, log_date=d, force_recompute=False)
        self.assertNotIn("skipped", r1)
        h1 = HeightLedger.objects.get(user=u, log_date=d, entry_type="daily_compute")
        first_cum = int(h1.cumulative_um)

        r2 = compute_daily_height_for_user(u, log_date=d, force_recompute=True)
        self.assertNotIn("skipped", r2)
        h2 = HeightLedger.objects.get(user=u, log_date=d, entry_type="daily_compute")
        self.assertEqual(int(h2.cumulative_um), first_cum)

    def test_rebuild_from_date_preserves_prior_days(self, mock_sub):
        mock_sub.return_value = MagicMock(
            data={"trial_day": None, "is_paid": True, "is_trial": False}
        )
        u = self._teen_user()
        d0 = date(2024, 6, 10)
        d1 = date(2024, 6, 11)
        DailyLog.objects.create(
            user=u,
            log_date=d0,
            exercise_points=0,
            food_points=0,
            lifestyle_points=0,
        )
        DailyLog.objects.create(
            user=u,
            log_date=d1,
            exercise_points=0,
            food_points=0,
            lifestyle_points=0,
        )
        compute_daily_height_for_user(u, log_date=d0)
        compute_daily_height_for_user(u, log_date=d1)
        self.assertEqual(
            HeightLedger.objects.filter(user=u, log_date__gte=d0).count(),
            2,
        )
        out = rebuild_ledger_from_date(u, d1)
        self.assertEqual(out["days_rebuilt"], 1)
        self.assertTrue(
            HeightLedger.objects.filter(user=u, log_date=d0, entry_type="daily_compute").exists()
        )
        self.assertEqual(
            HeightLedger.objects.filter(user=u, log_date=d1, entry_type="daily_compute").count(),
            1,
        )

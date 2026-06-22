"""Bug 14 — per-source daily points breakdown reconciles with engine cm."""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from users.spec_runtime import daily_points_source_breakdown


class DailyPointsBreakdownTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="breakdown_user",
            email="breakdown@example.com",
            password="testpass123",
        )

    def test_zero_log_day_reconciles_to_zero(self):
        sub = {"is_trial": False, "trial_day": None}
        bd = daily_points_source_breakdown(self.user, date(2026, 1, 15), age=25, subscription_data=sub)
        self.assertEqual(bd["tier"], "adult")
        self.assertEqual(bd["daily_points_total"], 0)
        self.assertEqual(bd["engine1"]["points"], 0)
        self.assertEqual(bd["engine2"]["points"], 0)
        # cm reconciliation: total == engine1 cm + engine2 cm.
        self.assertAlmostEqual(
            bd["engine_cm_uncapped_total"],
            round(bd["engine1"]["cm"] + bd["engine2"]["cm"], 6),
        )

    def test_breakdown_has_all_sources_and_caps(self):
        sub = {"is_trial": True, "trial_day": 2}
        bd = daily_points_source_breakdown(self.user, date(2026, 1, 15), age=15, subscription_data=sub)
        self.assertEqual(bd["tier"], "teen")
        for src in ("posture", "hgh", "food", "sleep", "sun", "meditation", "hydration"):
            self.assertIn(src, bd["raw_sources"])
        # Teen Engine-2 caps are documented for the audit.
        self.assertEqual(bd["engine2"]["caps"]["food"], 35)
        self.assertIsNone(bd["engine2"]["caps"]["hgh"])
        self.assertEqual(bd["engine1"]["cm_per_point"], 0.001)
        self.assertEqual(bd["engine2"]["cm_per_point"], 0.00005)

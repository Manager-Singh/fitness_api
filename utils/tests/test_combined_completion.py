"""Bug 11 — combined Lifestyle + Habits completion percentage math."""
from django.test import SimpleTestCase

from utils.combined_completion import (
    ADULT_NUTRITION_COMPLETION_MAX,
    TEEN_LIFESTYLE_COMPLETION_MAX,
    TEEN_LIFESTYLE_MAX_POINTS,
    _pct,
)


class CombinedCompletionMathTests(SimpleTestCase):
    def test_teen_lifestyle_max_is_29(self):
        self.assertEqual(TEEN_LIFESTYLE_MAX_POINTS, 29)
        self.assertEqual(TEEN_LIFESTYLE_COMPLETION_MAX["sleep"], 10)
        self.assertEqual(TEEN_LIFESTYLE_COMPLETION_MAX["water"], 10)
        self.assertEqual(TEEN_LIFESTYLE_COMPLETION_MAX["sunlight"], 7)
        self.assertEqual(TEEN_LIFESTYLE_COMPLETION_MAX["meditation"], 2)

    def test_teen_all_lifestyle_no_habits_is_about_71_percent(self):
        """Spec worked example: 29 of 41 → 71%, NOT 100%."""
        self.assertEqual(_pct(29, 41), 71)

    def test_teen_everything_done_is_100_percent(self):
        self.assertEqual(_pct(41, 41), 100)

    def test_nothing_logged_is_zero(self):
        self.assertEqual(_pct(0, 41), 0)

    def test_adult_nutrition_max_is_15(self):
        self.assertEqual(ADULT_NUTRITION_COMPLETION_MAX, 15)
        # Adult: all nutrition (15) but no habits → 15/27 ≈ 56%.
        self.assertEqual(_pct(15, 27), 56)

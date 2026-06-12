"""Adult optimization % must not count legacy lifestyle activity_score."""
from django.test import SimpleTestCase

from utils.optimization_pct import daily_optimization_from_breakdown


class AdultNoLifestyleDoubleCountTests(SimpleTestCase):
    def test_adult_ignores_activity_score_in_pool(self):
        result = daily_optimization_from_breakdown(
            {"food_score": 6, "activity_score": 10, "habit_score": 2},
            is_teen=False,
        )
        self.assertEqual(result["nutrition_earned"], 6)
        self.assertEqual(result["habits_earned"], 2)
        self.assertEqual(result["earned"], 8)
        self.assertNotIn("lifestyle_earned", result)

    def test_teen_includes_lifestyle_in_pool(self):
        result = daily_optimization_from_breakdown(
            {"food_score": 0, "activity_score": 1, "habit_score": 0},
            is_teen=True,
        )
        self.assertEqual(result["lifestyle_earned"], 1)
        self.assertEqual(result["percent"], 1)

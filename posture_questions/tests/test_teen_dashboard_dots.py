"""Section 5.10 — teen nutrition / lifestyle dot helpers."""

from django.test import SimpleTestCase

from utils.teen_dashboard_dots import (
    teen_lifestyle_nutrition_combined_percent,
    teen_nutrition_dots_from_food_points,
)


class TeenDashboardDotsTests(SimpleTestCase):
    def test_nutrition_dots_tiers(self):
        self.assertEqual(teen_nutrition_dots_from_food_points(0), 0)
        self.assertEqual(teen_nutrition_dots_from_food_points(5), 1)
        self.assertEqual(teen_nutrition_dots_from_food_points(10), 1)
        self.assertEqual(teen_nutrition_dots_from_food_points(11), 2)
        self.assertEqual(teen_nutrition_dots_from_food_points(31), 4)

    def test_combined_percent(self):
        self.assertEqual(teen_lifestyle_nutrition_combined_percent(4, 4), 100)
        self.assertEqual(teen_lifestyle_nutrition_combined_percent(1, 0), 12)

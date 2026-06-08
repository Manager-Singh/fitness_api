"""Part 2 §2.6 — adult nutrition (protein + hydration) scoring acceptance tests."""
from django.test import SimpleTestCase

from utils.adult_nutrition import (
    ADULT_NUTRITION_POINTS_CAP,
    adult_hydration_points,
    adult_nutrition_points,
    adult_protein_points,
)

W = 500  # one 500 ml water unit


class AdultProteinPointsTests(SimpleTestCase):
    def test_protein_scale_and_cap(self):
        self.assertEqual(adult_protein_points(90), 9)
        self.assertEqual(adult_protein_points(50), 5)
        self.assertEqual(adult_protein_points(200), 9)  # capped
        self.assertEqual(adult_protein_points(0), 0)
        self.assertEqual(adult_protein_points(19), 1)  # floor


class AdultHydrationPointsTests(SimpleTestCase):
    def test_spine_drinks_worth_double(self):
        self.assertEqual(adult_hydration_points(0, 3), 6)  # 3 spine -> 6
        self.assertEqual(adult_hydration_points(6 * W, 0), 6)  # 6 water -> 6
        self.assertEqual(adult_hydration_points(2 * W, 1), 4)  # 1 spine + 2 water -> 4
        self.assertEqual(adult_hydration_points(0, 4), 6)  # 4 spine -> capped 6

    def test_partial_water_unit_floors(self):
        self.assertEqual(adult_hydration_points(499, 0), 0)
        self.assertEqual(adult_hydration_points(501, 0), 1)


class AdultNutritionTotalTests(SimpleTestCase):
    def test_total_caps_at_15(self):
        self.assertEqual(adult_nutrition_points(90, 6 * W, 3), ADULT_NUTRITION_POINTS_CAP)
        self.assertEqual(adult_nutrition_points(90, 6 * W, 3), 15)
        # Never exceeds 15 even with huge inputs.
        self.assertLessEqual(adult_nutrition_points(1000, 100 * W, 100), 15)

    def test_typical_day(self):
        # 40 g protein (4) + 2 water (2) + 1 spine (2) = 8.
        self.assertEqual(adult_nutrition_points(40, 2 * W, 1), 8)

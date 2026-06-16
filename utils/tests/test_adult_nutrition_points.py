"""Monday F7 — adult nutrition tier scoring acceptance tests."""
from django.test import SimpleTestCase

from utils.adult_nutrition import (
    ADULT_NUTRITION_POINTS_CAP,
    adult_fluid_points,
    adult_fluid_points_raw,
    adult_nutrition_points_from_logs,
    adult_protein_points,
    tier_log_total,
)


class AdultProteinPointsTests(SimpleTestCase):
    def test_protein_scale_and_cap(self):
        self.assertEqual(adult_protein_points(90), 9)
        self.assertEqual(adult_protein_points(50), 5)
        self.assertEqual(adult_protein_points(200), 9)
        self.assertEqual(adult_protein_points(30), 3)


class AdultFluidPointsTests(SimpleTestCase):
    def test_tier1_worth_double(self):
        self.assertEqual(adult_fluid_points({"bone_broth": 3}, {}), 6)
        self.assertEqual(adult_fluid_points({}, {"water": 6}), 6)
        self.assertEqual(adult_fluid_points({"bone_broth": 1}, {"water": 2}), 4)
        self.assertEqual(adult_fluid_points({"bone_broth": 4}, {}), 6)

    def test_raw_uncapped(self):
        self.assertEqual(adult_fluid_points_raw({"bone_broth": 4}, {}), 8)


class AdultNutritionF7Tests(SimpleTestCase):
    def test_case_1_30g_three_tier1(self):
        # 30g protein (3) + 3 tier1 drinks (6 fluids) = 9
        total = adult_nutrition_points_from_logs(
            30,
            {"bone_broth": 1, "watermelon": 1, "coconut": 1},
            {},
        )
        self.assertEqual(total, 9)

    def test_case_2_max_protein_three_tier1(self):
        self.assertEqual(
            adult_nutrition_points_from_logs(90, {"bone_broth": 1, "watermelon": 1, "coconut": 1}, {}),
            15,
        )

    def test_case_3_six_waters(self):
        self.assertEqual(adult_nutrition_points_from_logs(0, {}, {"water": 6}), 6)

    def test_case_4_two_tier1_two_waters(self):
        self.assertEqual(
            adult_fluid_points({"bone_broth": 1, "watermelon": 1}, {"water": 2}),
            6,
        )

    def test_case_5_bone_broth_x4_caps_fluid_points(self):
        self.assertEqual(adult_fluid_points({"bone_broth": 4}, {}), 6)
        self.assertEqual(tier_log_total({"bone_broth": 4}), 4)

    def test_case_7_never_exceeds_15(self):
        self.assertLessEqual(
            adult_nutrition_points_from_logs(
                90,
                {"bone_broth": 10},
                {"water": 10, "milk": 10},
            ),
            ADULT_NUTRITION_POINTS_CAP,
        )

    def test_case_6_50g_one_tier1_two_waters(self):
        self.assertEqual(
            adult_nutrition_points_from_logs(50, {"bone_broth": 1}, {"water": 2}),
            9,
        )

"""Friday work order Task 1 — optimization % pool (68 teen / 27 adult)."""
from django.test import SimpleTestCase

from utils.optimization_pct import (
    ADULT_POOL,
    TEEN_POOL,
    daily_optimization_from_breakdown,
    _pct,
)


class OptimizationPctTests(SimpleTestCase):
    def test_teen_pool_is_68(self):
        self.assertEqual(TEEN_POOL, 68)

    def test_adult_pool_is_27(self):
        self.assertEqual(ADULT_POOL, 27)

    def test_one_lifestyle_point_teen_is_about_1_percent(self):
        result = daily_optimization_from_breakdown(
            {"food_score": 0, "activity_score": 1, "habit_score": 0},
            is_teen=True,
        )
        self.assertEqual(result["percent"], _pct(1, 68))
        self.assertEqual(result["percent"], 1)

    def test_teen_full_pool_is_100(self):
        result = daily_optimization_from_breakdown(
            {"food_score": 35, "activity_score": 21, "habit_score": 12},
            is_teen=True,
        )
        self.assertEqual(result["earned"], 68)
        self.assertEqual(result["percent"], 100)

    def test_teen_caps_applied_before_sum(self):
        result = daily_optimization_from_breakdown(
            {"food_score": 50, "activity_score": 30, "habit_score": 20},
            is_teen=True,
        )
        self.assertEqual(result["earned"], 68)
        self.assertEqual(result["percent"], 100)

    def test_adult_half_nutrition_no_habits(self):
        result = daily_optimization_from_breakdown(
            {"food_score": 15, "activity_score": 0, "habit_score": 0},
            is_teen=False,
        )
        self.assertEqual(result["percent"], 56)

    def test_adult_full_pool_is_100(self):
        result = daily_optimization_from_breakdown(
            {"food_score": 15, "habit_score": 12},
            is_teen=False,
        )
        self.assertEqual(result["percent"], 100)

    def test_nothing_logged_is_zero(self):
        self.assertEqual(
            daily_optimization_from_breakdown({}, is_teen=True)["percent"],
            0,
        )

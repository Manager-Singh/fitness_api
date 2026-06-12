"""Combined completion delegates to Friday Task 1 optimization pool."""
from django.test import SimpleTestCase

from utils.combined_completion import (
    ADULT_NUTRITION_COMPLETION_MAX,
    TEEN_POOL,
    _pct,
)
from utils.optimization_pct import TEEN_NUTRITION_CAP, TEEN_LIFESTYLE_CAP, TEEN_HABITS_CAP


class CombinedCompletionMathTests(SimpleTestCase):
    def test_teen_pool_constants(self):
        self.assertEqual(TEEN_NUTRITION_CAP, 35)
        self.assertEqual(TEEN_LIFESTYLE_CAP, 21)
        self.assertEqual(TEEN_HABITS_CAP, 12)
        self.assertEqual(TEEN_POOL, 68)

    def test_one_point_teen_is_about_1_percent(self):
        self.assertEqual(_pct(1, 68), 1)

    def test_teen_everything_done_is_100_percent(self):
        self.assertEqual(_pct(68, 68), 100)

    def test_nothing_logged_is_zero(self):
        self.assertEqual(_pct(0, 68), 0)

    def test_adult_nutrition_max_is_15(self):
        self.assertEqual(ADULT_NUTRITION_COMPLETION_MAX, 15)
        self.assertEqual(_pct(15, 27), 56)

import unittest

from utils.graph_age_projection import (
    calculate_height_projection,
    floor_teen_projection_targets,
)


class FloorTeenProjectionTargetsTests(unittest.TestCase):
    def test_floors_when_current_exceeds_mph(self):
        genetic, optimized, unoptimized = floor_teen_projection_targets(
            163.0,
            135.0,
            139.6,
            133.0,
            posture_boost_cm=4.6,
        )
        self.assertEqual(genetic, 163.0)
        self.assertEqual(optimized, 167.6)
        self.assertEqual(unoptimized, 161.0)


class CalculateHeightProjectionTests(unittest.TestCase):
    def test_female_18_chart_ends_at_or_above_current(self):
        chart = calculate_height_projection(
            163.0,
            139.6,
            135.0,
            133.0,
            "female",
            age_exact=18.0,
        )
        ages = sorted(chart["data"].keys())
        self.assertEqual(ages[-1], 18)
        last = chart["data"][ages[-1]]
        self.assertGreaterEqual(last["genetic"], 163.0)
        self.assertGreaterEqual(last["optimized"], 163.0)
        self.assertGreaterEqual(chart["maxY"], 170)

    def test_female_18_last_age_meets_or_exceeds_floored_genetic(self):
        chart = calculate_height_projection(
            163.0,
            139.6,
            135.0,
            133.0,
            "female",
            age_exact=18.0,
        )
        genetic_vals = [chart["data"][a]["genetic"] for a in sorted(chart["data"])]
        self.assertGreaterEqual(genetic_vals[-1], 163.0)
        self.assertGreater(genetic_vals[-1], genetic_vals[0])

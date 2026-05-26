import unittest
from types import SimpleNamespace

import utils.adult_nutrition as adult_nutrition


class AdultNutritionBucketTests(unittest.TestCase):
    def test_catalog_fallback_counts_food_when_module_is_teen(self):
        catalog = {9: "muscle", 15: "muscle", 1: "muscle", 12: "muscle"}
        orig = adult_nutrition.adult_catalog_food_bucket_map
        orig_plan = adult_nutrition.adult_plan_module_buckets
        try:
            adult_nutrition.adult_plan_module_buckets = lambda: {}
            adult_nutrition.adult_catalog_food_bucket_map = lambda: dict(catalog)
            entries = [
                SimpleNamespace(
                    food_id=9,
                    module=SimpleNamespace(name="GrowthMax Teen", nutrition_category="teen"),
                ),
                SimpleNamespace(
                    food_id=15,
                    module=SimpleNamespace(name="GrowthMax Teen", nutrition_category="teen"),
                ),
                SimpleNamespace(
                    food_id=1,
                    module=SimpleNamespace(name="GrowthMax Teen", nutrition_category="teen"),
                ),
            ]
            disc, muscle = adult_nutrition.adult_disc_muscle_food_id_sets(entries)
            self.assertEqual(disc, set())
            self.assertEqual(muscle, {9, 15, 1})
        finally:
            adult_nutrition.adult_catalog_food_bucket_map = orig
            adult_nutrition.adult_plan_module_buckets = orig_plan

    def test_adult_plan_module_id_assigns_bucket(self):
        plan = {42: "muscle"}
        orig = adult_nutrition.adult_plan_module_buckets
        orig_cat = adult_nutrition.adult_catalog_food_bucket_map
        try:
            adult_nutrition.adult_plan_module_buckets = lambda: dict(plan)
            adult_nutrition.adult_catalog_food_bucket_map = lambda: {}
            entries = [
                SimpleNamespace(
                    food_id=99,
                    module=SimpleNamespace(
                        id=42,
                        name="Posture Muscle Repair & Fuel Foods",
                        nutrition_category="muscle",
                    ),
                ),
            ]
            disc, muscle = adult_nutrition.adult_disc_muscle_food_id_sets(entries)
            self.assertEqual(disc, set())
            self.assertEqual(muscle, {99})
        finally:
            adult_nutrition.adult_plan_module_buckets = orig
            adult_nutrition.adult_catalog_food_bucket_map = orig_cat

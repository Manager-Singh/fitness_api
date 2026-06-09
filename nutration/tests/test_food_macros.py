"""Tests for protein/calories in nutrition plan and log APIs."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from nutration.food_macros import food_macros_from_entries, hydration_summary_for_user
from nutration.models import AgeGroup, Food, Module, ModuleFood
from nutration.models_log import AdultNutritionDay, NutraEntry, NutraSession
from nutration.views import MyPlanView
from nutration.views_log import NutraLogViewSet
from user_profile.models import UserProfile
from utils.age import get_user_age, get_user_age_exact
from utils.paywall_flags import is_adult_age
from utils.user_time import user_today

User = get_user_model()


class FoodMacroTotalsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="macro_user",
            email="macro_user@test.example",
            password="secret123",
        )
        prof, _ = UserProfile.objects.get_or_create(user=self.user)
        prof.gender = "female"
        prof.birth_date = date(2010, 6, 9)
        prof.save()
        self.user.account_tier = "teen"
        self.user.save()
        self.user.refresh_from_db()

        self.assertLess(get_user_age(self.user), 18)
        self.assertFalse(is_adult_age(get_user_age_exact(self.user), get_user_age(self.user), user=self.user))

        self.log_date = user_today(self.user)
        self.ag = AgeGroup.objects.create(name="13-20", min_age=13, max_age=20)
        self.mod = Module.objects.create(
            name="Growth Boost",
            type=Module.NUTRITION,
            age_group=self.ag,
            nutrition_category="teen",
        )
        self.banana = Food.objects.create(
            name="Bananas",
            short_name="Bananas",
            calories=105,
            protein=Decimal("1.30"),
        )
        ModuleFood.objects.create(module=self.mod, food=self.banana, score=5)
        self.session = NutraSession.objects.create(user=self.user, date=self.log_date)
        NutraEntry.objects.create(
            session=self.session,
            module=self.mod,
            food=self.banana,
            score=5,
        )

    def test_food_macros_from_entries(self):
        entries = NutraEntry.objects.filter(session=self.session).select_related("food")
        totals = food_macros_from_entries(entries)
        self.assertEqual(totals["today_total_calories"], 105)
        self.assertAlmostEqual(totals["today_total_protein"], 1.30)

    @patch("nutration.views.check_subscription_or_response")
    def test_my_nutrition_plan_includes_macros_on_foods_and_totals(self, mock_sub):
        mock_sub.return_value.data = {"is_paid": True, "expired": False}

        factory = APIRequestFactory()
        req = factory.get("/api/my-nutrition-plan?type=nutrition")
        force_authenticate(req, user=self.user)
        resp = MyPlanView.as_view()(req)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["today_total_calories"], 105)
        self.assertAlmostEqual(resp.data["today_total_protein"], 1.30)
        self.assertIn("hydration_today", resp.data)
        self.assertEqual(resp.data["hydration_today"]["tracking"], "lifestyle")

        all_foods = [
            food
            for module in (resp.data.get("nutrition") or [])
            for food in (module.get("foods") or [])
        ]
        self.assertTrue(all_foods, msg="expected at least one food in nutrition plan")
        banana = next(f for f in all_foods if f["name"] == "Bananas")
        self.assertEqual(banana["calories"], 105)
        self.assertAlmostEqual(banana["protein"], 1.30)

    @patch("nutration.views_log.check_subscription_or_response")
    def test_nutra_log_create_returns_macro_totals(self, mock_sub):
        mock_sub.return_value.data = {"is_paid": True, "expired": False}
        NutraEntry.objects.filter(session=self.session).delete()

        factory = APIRequestFactory()
        req = factory.post(
            "/api/nutra-logs",
            {"food_id": self.banana.id, "module_id": self.mod.id},
            format="json",
        )
        force_authenticate(req, user=self.user)
        resp = NutraLogViewSet.as_view({"post": "create"})(req)

        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["today_total_calories"], 105)
        self.assertAlmostEqual(resp.data["today_total_protein"], 1.30)
        self.assertIn("hydration_today", resp.data)
        self.assertEqual(resp.data["hydration_today"]["tracking"], "lifestyle")


class AdultHydrationSummaryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="hyd_user",
            email="hyd_user@test.example",
            password="secret123",
        )
        self.user.account_tier = "adult"
        self.user.save()
        prof, _ = UserProfile.objects.get_or_create(user=self.user)
        prof.gender = "male"
        prof.birth_date = date.today() - timedelta(days=int(365.2425 * 25))
        prof.save()

    def test_hydration_log_entries_expand_per_500ml_tap(self):
        from utils.adult_nutrition import build_hydration_log_entries

        logs = build_hydration_log_entries(3000, [])
        self.assertEqual(len(logs), 6)
        self.assertTrue(all(e["label"] == "500 ml" for e in logs))

    def test_adult_hydration_ml_totals(self):
        AdultNutritionDay.objects.create(
            user=self.user,
            log_date=date.today(),
            water_ml=1000,
            spine_500ml_count=2,
            spine_drinks=[{"type": "bone_broth", "count": 2}],
        )
        summary = hydration_summary_for_user(
            self.user, date.today(), adult_nutrition_plan=True
        )
        self.assertEqual(summary["tracking"], "ml")
        self.assertEqual(summary["water_ml"], 1000)
        self.assertEqual(summary["spine_500ml_count"], 2)
        self.assertEqual(summary["total_ml"], 2000)
        self.assertEqual(len(summary["logs"]), 4)
        self.assertEqual(summary["today_logged_hydration"][:2], ["500 ml", "500 ml"])
        self.assertTrue(all("Bone Broth" in label for label in summary["today_logged_hydration"][2:]))

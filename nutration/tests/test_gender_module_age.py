"""Gender-specific adult module visibility (female 18+, male 21+)."""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from nutration.models import Activity, AgeGroup, Module, ModuleActivity
from nutration.views import MyPlanView
from user_profile.models import UserProfile
from utils.nutrition_plan import module_filter_age

User = get_user_model()


def _paid_subscription():
    return {"expired": False, "is_paid": True, "is_trial": False, "trial_day": None}


class GenderModuleAgeTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.teen_ag = AgeGroup.objects.create(name="Age 13-20", min_age=13, max_age=20)
        self.adult_ag = AgeGroup.objects.create(name="21+", min_age=21, max_age=None)
        self.hydration_mod = Module.objects.create(
            name="Adult Hydration",
            short_name="Adult Hydration",
            type=Module.LIFESTYLE,
            age_group=self.adult_ag,
            sort_order=1,
        )
        act = Activity.objects.create(name="Water Log", short_name="Water")
        ModuleActivity.objects.create(module=self.hydration_mod, activity=act, score=1)

    def _user(self, *, suffix: str, birth_date: date, gender: str, tier: str):
        u = User.objects.create_user(
            username=f"mod_{suffix}",
            email=f"mod_{suffix}@test.example",
            password="secret123",
        )
        prof, _ = UserProfile.objects.get_or_create(user=u)
        prof.gender = gender
        prof.birth_date = birth_date
        prof.save()
        u.account_tier = tier
        u.save()
        u.refresh_from_db()
        return u

    def test_female_adult_19_uses_plan_age_21(self):
        user = self._user(
            suffix="f19",
            birth_date=date.today() - timedelta(days=int(365.2425 * 19)),
            gender="female",
            tier="adult",
        )
        user.refresh_from_db()
        from utils.age import get_user_age, get_user_age_exact

        age = get_user_age(user)
        age_exact = get_user_age_exact(user)
        self.assertGreaterEqual(age_exact, 18.0)
        self.assertEqual(module_filter_age(user, age, age_exact=age_exact), 21)

    def test_male_teen_20_keeps_plan_age_20(self):
        user = self._user(
            suffix="m20",
            birth_date=date.today() - timedelta(days=int(365.2425 * 20)),
            gender="male",
            tier="teen",
        )
        user.refresh_from_db()
        from utils.age import get_user_age, get_user_age_exact

        age = get_user_age(user)
        age_exact = get_user_age_exact(user)
        self.assertLess(age_exact, 21.0)
        self.assertEqual(module_filter_age(user, age, age_exact=age_exact), age)

    @patch("nutration.views.check_subscription_or_response")
    def test_female_adult_19_sees_adult_hydration_module(self, mock_sub):
        user = self._user(
            suffix="f19api",
            birth_date=date.today() - timedelta(days=int(365.2425 * 19)),
            gender="female",
            tier="adult",
        )
        user.refresh_from_db()
        mock_sub.return_value.data = _paid_subscription()

        req = self.factory.get("/api/my-nutrition-plan?type=lifestyle")
        force_authenticate(req, user=user)
        resp = MyPlanView.as_view()(req)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["adult_min"], 18.0)
        self.assertEqual(resp.data["plan_age"], 21)
        module_ids = [m["module_id"] for m in (resp.data.get("lifestyle") or [])]
        self.assertIn(self.hydration_mod.id, module_ids)

    @patch("nutration.views.check_subscription_or_response")
    def test_male_teen_20_does_not_see_adult_hydration_module(self, mock_sub):
        user = self._user(
            suffix="m20api",
            birth_date=date.today() - timedelta(days=int(365.2425 * 20)),
            gender="male",
            tier="teen",
        )
        user.refresh_from_db()
        mock_sub.return_value.data = _paid_subscription()

        req = self.factory.get("/api/my-nutrition-plan?type=lifestyle")
        force_authenticate(req, user=user)
        resp = MyPlanView.as_view()(req)

        self.assertEqual(resp.status_code, 200)
        module_ids = [m["module_id"] for m in (resp.data.get("lifestyle") or [])]
        self.assertNotIn(self.hydration_mod.id, module_ids)

"""Nutrition plan + daily_points score tests."""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from habits.models import MicroHabit, MicroHabitLog
from nutration.models import Activity, AgeGroup, Module, ModuleActivity
from nutration.models_log import NutraEntry, NutraSession
from nutration.views import MyPlanView
from user_profile.models import UserProfile
from utils.scores_summary import get_today_daily_points, today_score_breakdown

User = get_user_model()


def _paid_subscription():
    return {
        "expired": False,
        "is_paid": True,
        "is_trial": False,
        "trial_day": None,
    }


class AdultPaidLifestylePlanTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.teen_ag = AgeGroup.objects.create(name="13-20", min_age=13, max_age=20)
        self.life_mod = Module.objects.create(
            name="Sleep Recovery",
            short_name="Sleep",
            type=Module.LIFESTYLE,
            age_group=self.teen_ag,
            sort_order=1,
        )
        act = Activity.objects.create(name="Early Bed", short_name="Bed")
        ModuleActivity.objects.create(module=self.life_mod, activity=act, score=5)

    def _adult_user(self, *, email_suffix: str, birth_years: float, gender: str):
        u = User.objects.create_user(
            username=f"adult_{email_suffix}",
            email=f"adult_{email_suffix}@test.example",
            password="secret123",
        )
        prof, _ = UserProfile.objects.get_or_create(user=u)
        prof.gender = gender
        prof.birth_date = date.today() - timedelta(days=int(365.2425 * birth_years))
        prof.save()
        u.account_tier = "adult"
        u.save()
        return u

    @patch("nutration.views.check_subscription_or_response")
    def test_male_adult_22_paid_sees_lifestyle(self, mock_sub):
        user = self._adult_user(email_suffix="m22", birth_years=22.0, gender="male")
        mock_sub.return_value.data = _paid_subscription()

        req = self.factory.get("/api/my-nutrition-plan?type=lifestyle")
        force_authenticate(req, user=user)
        resp = MyPlanView.as_view()(req)

        self.assertEqual(resp.status_code, 200)
        self.assertGreater(len(resp.data.get("lifestyle") or []), 0)
        self.assertEqual(resp.data["lifestyle"][0]["module_id"], self.life_mod.id)

    @patch("nutration.views.check_subscription_or_response")
    def test_female_adult_19_paid_sees_lifestyle(self, mock_sub):
        user = self._adult_user(email_suffix="f19", birth_years=19.0, gender="female")
        mock_sub.return_value.data = _paid_subscription()

        req = self.factory.get("/api/my-nutrition-plan?type=lifestyle")
        force_authenticate(req, user=user)
        resp = MyPlanView.as_view()(req)

        self.assertEqual(resp.status_code, 200)
        self.assertGreater(len(resp.data.get("lifestyle") or []), 0)

    @patch("nutration.views.check_subscription_or_response")
    def test_male_adult_22_unpaid_lifestyle_empty_when_outside_age_band(self, mock_sub):
        user = self._adult_user(email_suffix="m22free", birth_years=22.0, gender="male")
        mock_sub.return_value.data = {
            "expired": False,
            "is_paid": False,
            "is_trial": False,
        }

        req = self.factory.get("/api/my-nutrition-plan?type=lifestyle")
        force_authenticate(req, user=user)
        resp = MyPlanView.as_view()(req)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data.get("lifestyle") or [], [])


class DailyPointsIncludesHabitsAndLifestyleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="pts_user",
            email="pts_user@test.example",
            password="secret123",
        )
        prof, _ = UserProfile.objects.get_or_create(user=self.user)
        prof.gender = "female"
        prof.birth_date = date.today() - timedelta(days=int(365.2425 * 16))
        prof.save()
        self.ag = AgeGroup.objects.create(name="13-20", min_age=13, max_age=20)
        self.life_mod = Module.objects.create(
            name="Sunlight Exposure",
            short_name="Sun",
            type=Module.LIFESTYLE,
            age_group=self.ag,
        )
        act = Activity.objects.create(name="Sun AM", short_name="Sun")
        ModuleActivity.objects.create(module=self.life_mod, activity=act, score=6)
        habit, _ = MicroHabit.objects.get_or_create(
            code="tech_neck_lift",
            defaults={
                "name": "Tech-Neck",
                "logging_mode": "once_daily",
                "points_per_log": 2,
            },
        )
        MicroHabitLog.objects.create(
            user=self.user,
            log_date=date.today(),
            habit=habit,
            slot="once",
            points=2,
        )

    def test_today_daily_points_includes_lifestyle_and_habits(self):
        session = NutraSession.objects.create(user=self.user, date=date.today())
        activity = Activity.objects.get(name="Sun AM")
        NutraEntry.objects.create(
            session=session,
            module=self.life_mod,
            activity=activity,
            score=6,
        )

        sub = _paid_subscription()
        total = get_today_daily_points(self.user, sub)
        breakdown = today_score_breakdown(self.user, sub)
        self.assertGreaterEqual(total, 8)  # 6 lifestyle + 2 habits (capped)
        self.assertEqual(breakdown["lifestyle_score"], 6)
        self.assertEqual(breakdown["habit_score"], 2)
        self.assertEqual(breakdown["total_score"], total)

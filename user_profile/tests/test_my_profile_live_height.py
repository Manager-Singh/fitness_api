from datetime import date, timedelta

from django.test import TestCase
from rest_framework.test import APIClient

from user_profile.models import UserProfile
from users.models import HeightLedger, PostureState, User


class MyProfileLiveHeightTests(TestCase):
    def test_my_profile_returns_height_live_cm_from_ledger(self):
        u = User.objects.create_user(
            username="p1",
            email="p1@test.example",
            password="secret123",
        )
        prof, _ = UserProfile.objects.get_or_create(user=u)
        prof.gender = "male"
        prof.base_height_cm = "160"
        prof.current_height_cm = "160"
        prof.birth_date = date.today() - timedelta(days=int(365.2425 * 15))
        prof.save()

        # Ensure runtime state exists and is unlocked (does not affect snapshot math, but mirrors real env).
        ps, _ = PostureState.objects.get_or_create(user=u)
        ps.scan_completed = True
        ps.questionnaire_completed = True
        ps.save()

        # cumulative_um is cumulative gain (not including base height).
        HeightLedger.objects.create(
            user=u,
            log_date=date.today(),
            entry_type="daily_compute",
            delta_um=0,
            cumulative_um=10000,  # +1.000 cm
            engine1_delta_um=0,
            bio_delta_um=0,
            engine2_delta_dm=0,
            algorithm_version="v1",
            metadata={},
        )

        client = APIClient()
        client.force_authenticate(user=u)
        resp = client.get("/api/my-profile")
        self.assertEqual(resp.status_code, 200, resp.data)
        height_live = (resp.data.get("data") or {}).get("profile", {}).get("height_live_cm")
        self.assertEqual(height_live, 161.0)

    def test_my_profile_age_exact_and_local_calendar(self):
        u = User.objects.create_user(
            username="p2",
            email="p2@test.example",
            password="secret123",
        )
        u.timezone = "America/New_York"
        u.save(update_fields=["timezone"])
        prof, _ = UserProfile.objects.get_or_create(user=u)
        prof.gender = "male"
        prof.base_height_cm = "160"
        prof.birth_date = date(2010, 3, 15)
        prof.save()

        client = APIClient()
        client.force_authenticate(user=u)
        resp = client.get("/api/my-profile")
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data.get("data") or {}
        prof_out = data.get("profile") or {}
        self.assertEqual(prof_out.get("base_height_label"), "Starting Height")
        age_exact = prof_out.get("age_exact")
        self.assertIsInstance(age_exact, dict)
        self.assertIn("years", age_exact)
        self.assertIn("days_since_last_birthday", age_exact)
        self.assertIn("label", age_exact)
        self.assertTrue(str(age_exact.get("label", "")).endswith("days old"))
        cal = data.get("local_calendar") or {}
        self.assertIn("today_date", cal)
        self.assertIn("weekday", cal)


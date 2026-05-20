from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()


class LeaderboardCountryFlagTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.viewer = User.objects.create_user(
            email="viewer@example.com",
            username="viewer@example.com",
            password="pass12345",
            country_code="US",
        )
        self.peer = User.objects.create_user(
            email="peer@example.com",
            username="peer@example.com",
            password="pass12345",
            country_code="CA",
        )
        self.client.force_authenticate(user=self.viewer)

    def test_leaderboard_entry_includes_country_code_and_flag(self):
        resp = self.client.get("/api/leaderboard/", {"view": "alltime"})
        self.assertEqual(resp.status_code, 200)
        entries = resp.data.get("entries") or []
        by_id = {e["user_id"]: e for e in entries}
        self.assertIn(self.viewer.id, by_id)
        row = by_id[self.viewer.id]
        self.assertEqual(row.get("country_code"), "US")
        self.assertEqual(row.get("country_flag_emoji"), "🇺🇸")

    def test_register_defaults_country_code_to_ca(self):
        from users.serializers import RegisterSerializer

        email = "newuser@example.com"
        serializer = RegisterSerializer(
            data={"email": email, "password": "pass12345"},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()
        self.assertEqual(user.country_code, "CA")

    def test_register_accepts_explicit_country_code(self):
        from users.serializers import RegisterSerializer

        serializer = RegisterSerializer(
            data={
                "email": "gbuser@example.com",
                "password": "pass12345",
                "country_code": "gb",
            },
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()
        self.assertEqual(user.country_code, "GB")

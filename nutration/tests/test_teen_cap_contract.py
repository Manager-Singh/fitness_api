from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from nutration.models import AgeGroup, Food, Module
from nutration.models_log import NutraEntry, NutraSession
from user_profile.models import UserProfile
from users.models import PostureState, User
from utils.teen_nutrition_cap import TEEN_CAP_MESSAGE_EXACT


@patch("nutration.views_log.check_subscription_or_response")
class TeenNutritionCapContractTests(TestCase):
    def _teen_user(self):
        u = User.objects.create_user(
            username="capteen",
            email="capteen@test.example",
            password="secret123",
        )
        prof, _ = UserProfile.objects.get_or_create(user=u)
        prof.gender = "male"
        prof.base_height_cm = "160"
        prof.current_height_cm = "160"
        prof.birth_date = date.today() - timedelta(days=int(365.2425 * 15))
        prof.save()
        # Mark as teen tier (mirrors the adult fixtures setting account_tier).
        # Avoids relying on the stale reverse-OneToOne profile cache for age.
        u.account_tier = "teen"
        u.save(update_fields=["account_tier"])
        ps, _ = PostureState.objects.get_or_create(user=u)
        ps.scan_completed = True
        ps.questionnaire_completed = True
        ps.save()
        return u

    def test_cap_message_exact_and_once_per_day_gating(self, mock_sub):
        mock_sub.return_value = MagicMock(data={"is_paid": True, "expired": False})
        u = self._teen_user()
        client = APIClient()
        client.force_authenticate(user=u)

        # Minimal module/food to allow NutraEntry creation.
        teen_ag = AgeGroup.objects.create(name="13-20", min_age=13, max_age=20)
        mod = Module.objects.create(
            name="Teen Module",
            type=Module.NUTRITION,
            nutrition_category="teen",
            age_group=teen_ag,
        )
        food = Food.objects.create(name="Food A", short_name="A")

        today = date.today()
        session = NutraSession.objects.create(user=u, date=today)
        # Seed 34 points before call. Backdate past the 2s double-tap dedup
        # window so the crossing POST below is not dropped as a duplicate.
        seed = NutraEntry.objects.create(session=session, module=mod, food=food, score=34)
        NutraEntry.objects.filter(pk=seed.pk).update(
            completed_at=timezone.now() - timedelta(seconds=30)
        )

        # Post that crosses to 35.
        resp = client.post(
            "/api/nutra-logs",
            data={"food_activity": {"module": mod.id, "food": food.id, "score": 1}},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data.get("teen_nutrition_cap_message"), TEEN_CAP_MESSAGE_EXACT)
        self.assertTrue(resp.data.get("teen_nutrition_cap_modal_required"))

        # Second post same day (already reached) should not require modal again.
        resp2 = client.post(
            "/api/nutra-logs",
            data={"food_activity": {"module": mod.id, "food": food.id, "score": 1}},
            format="json",
        )
        self.assertEqual(resp2.status_code, 201, resp2.data)
        self.assertEqual(resp2.data.get("teen_nutrition_cap_message"), TEEN_CAP_MESSAGE_EXACT)
        self.assertFalse(resp2.data.get("teen_nutrition_cap_modal_required"))


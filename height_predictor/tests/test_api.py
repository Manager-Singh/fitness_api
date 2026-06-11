"""
API + integration tests for the Ultimate Height Predictor.

Covers: POST computes/stores/returns a number; posture is read from PostureState; GET returns
the latest result; missing core inputs -> 422; and the dashboard fallback query selects the
latest completed prediction (the exact expression used in posture_questions.views).
"""
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from height_predictor.models import UltimateHeightPrediction

User = get_user_model()


class _Base(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="teen1", email="teen1@example.com", password="pw12345!")
        self.client.force_authenticate(self.user)
        self.url = reverse("ultimate-height-predictor")

    def _make_profile(self, **overrides):
        from user_profile.models import UserProfile

        defaults = dict(
            gender="male", age="14", current_height_cm="160",
            father_height_cm="180", mother_height_cm="166",
        )
        defaults.update(overrides)
        obj, _ = UserProfile.objects.update_or_create(user=self.user, defaults=defaults)
        return obj

    def _make_posture(self, um):
        from users.models import PostureState

        obj, _ = PostureState.objects.update_or_create(
            user=self.user, defaults={"total_recoverable_loss_um": um}
        )
        return obj


class PredictorApiTests(_Base):
    def test_post_computes_and_stores(self):
        self._make_profile()
        self._make_posture(30000)  # 3.0 cm
        resp = self.client.post(
            self.url,
            {"age_years": 14.5, "voice_depth": 1, "facial_hair": 1, "body_hair": 1, "adams_apple": 0},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertTrue(resp.data["completed"])
        result = resp.data["result"]
        self.assertEqual(result["band"], "A")
        self.assertAlmostEqual(result["posture_recovery_cm"], 3.0, delta=0.01)
        self.assertAlmostEqual(result["true_optimized_cm"], 177.3, delta=0.3)
        self.assertEqual(UltimateHeightPrediction.objects.filter(user=self.user, completed=True).count(), 1)

    def test_posture_read_from_posture_state(self):
        self._make_profile()
        self._make_posture(50000)  # 5.0 cm
        resp = self.client.post(self.url, {"age_years": 14.5, "voice_depth": 1}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertAlmostEqual(resp.data["result"]["posture_recovery_cm"], 5.0, delta=0.01)

    def test_post_without_posture_state_defaults_zero(self):
        self._make_profile()
        resp = self.client.post(self.url, {"age_years": 14.5}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data["result"]["posture_recovery_cm"], 0.0)

    def test_missing_core_inputs_returns_422(self):
        # No profile, and request omits parent heights -> cannot compute.
        resp = self.client.post(self.url, {"age_years": 15.0, "sex": "male", "current_height_cm": 165}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertIn("father_height_cm", resp.data["missing"])

    def test_client_values_override_profile(self):
        self._make_profile(current_height_cm="160")
        resp = self.client.post(
            self.url,
            {"age_years": 14.5, "current_height_cm": 170, "voice_depth": 1},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        pred = UltimateHeightPrediction.objects.get(user=self.user)
        self.assertEqual(pred.current_height_cm, 170)

    def test_get_returns_latest_result(self):
        self._make_profile()
        self._make_posture(20000)
        self.client.post(self.url, {"age_years": 14.5, "voice_depth": 1}, format="json")
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["completed"])
        self.assertIsNotNone(resp.data["result"]["true_optimized_cm"])

    def test_get_before_any_assessment(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["completed"])
        self.assertIsNone(resp.data["result"])

    def test_invalid_input_rejected(self):
        self._make_profile()
        resp = self.client.post(self.url, {"menarche_status": 9}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class FallbackSelectionTests(_Base):
    def _branch_value(self, existing_value):
        """Replicate the exact selection used in posture_questions.views fallback branch."""
        optimized_height_for_ui = existing_value
        pred = (
            UltimateHeightPrediction.objects.filter(user=self.user, completed=True)
            .order_by("-computed_at")
            .first()
        )
        if pred and pred.true_optimized_cm:
            optimized_height_for_ui = pred.true_optimized_cm
        return optimized_height_for_ui

    def test_uses_existing_value_when_no_prediction(self):
        self.assertEqual(self._branch_value(170.0), 170.0)

    def test_uses_prediction_when_completed(self):
        UltimateHeightPrediction.objects.create(user=self.user, true_optimized_cm=181.6, completed=True)
        self.assertEqual(self._branch_value(170.0), 181.6)

    def test_ignores_incomplete_prediction(self):
        UltimateHeightPrediction.objects.create(user=self.user, true_optimized_cm=999.0, completed=False)
        self.assertEqual(self._branch_value(170.0), 170.0)

    def test_latest_completed_wins(self):
        UltimateHeightPrediction.objects.create(user=self.user, true_optimized_cm=175.0, completed=True)
        UltimateHeightPrediction.objects.create(user=self.user, true_optimized_cm=182.0, completed=True)
        self.assertEqual(self._branch_value(170.0), 182.0)

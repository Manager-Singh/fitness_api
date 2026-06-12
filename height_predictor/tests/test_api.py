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
        # Auto-created profile has regional parent fallbacks; still need sex/age/height.
        from user_profile.models import UserProfile

        prof = UserProfile.objects.get(user=self.user)
        prof.gender = ""
        prof.age = None
        prof.current_height_cm = None
        prof.base_height_cm = None
        prof.save()
        resp = self.client.post(self.url, {"voice_depth": 1}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        missing = set(resp.data.get("missing") or [])
        self.assertTrue(missing & {"sex", "age_years", "current_height_cm"})

    def test_null_parents_use_regional_fallback(self):
        self.user.country_code = "US"
        self.user.save(update_fields=["country_code"])
        self._make_profile(father_height_cm=None, mother_height_cm=None)
        self._make_posture(20000)
        resp = self.client.post(self.url, {"age_years": 14.5, "voice_depth": 1}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        pred = UltimateHeightPrediction.objects.get(user=self.user)
        self.assertAlmostEqual(pred.father_height_cm, 175.0, delta=0.1)
        self.assertAlmostEqual(pred.mother_height_cm, 162.0, delta=0.1)

    def test_band_b_requires_recent_growth(self):
        self._make_profile(age="19")
        self._make_posture(20000)
        resp = self.client.post(self.url, {"age_years": 19.0}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertIn("recent_growth_cm", resp.data["missing"])

    def test_band_b_with_recent_growth_succeeds(self):
        self._make_profile(age="19")
        self._make_posture(20000)
        resp = self.client.post(
            self.url,
            {"age_years": 19.0, "recent_growth_cm": 2.0},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data["result"]["band"], "B")

    def test_assessment_prefill_endpoint(self):
        self._make_profile()
        self._make_posture(42000)
        url = reverse("ultimate-height-prefill")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["sex"], "Male")
        self.assertIn("exact_age", resp.data)
        self.assertAlmostEqual(resp.data["posture_recovery_cm"], 4.2, delta=0.1)
        self.assertFalse(resp.data["predictor_completed"])

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
    def _branch_value(self):
        """Replicate green-line selection in posture_questions.views (predictor-only)."""
        from height_predictor.services import get_latest_prediction

        optimized_height_for_ui = None
        pred = get_latest_prediction(self.user)
        if pred and pred.completed and pred.true_optimized_cm:
            optimized_height_for_ui = pred.true_optimized_cm
        return optimized_height_for_ui

    def test_no_prediction_returns_none(self):
        self.assertIsNone(self._branch_value())

    def test_uses_prediction_when_completed(self):
        UltimateHeightPrediction.objects.create(user=self.user, true_optimized_cm=181.6, completed=True)
        self.assertEqual(self._branch_value(), 181.6)

    def test_ignores_incomplete_prediction(self):
        UltimateHeightPrediction.objects.create(user=self.user, true_optimized_cm=999.0, completed=False)
        self.assertIsNone(self._branch_value())

    def test_latest_completed_wins(self):
        UltimateHeightPrediction.objects.create(user=self.user, true_optimized_cm=175.0, completed=True)
        UltimateHeightPrediction.objects.create(user=self.user, true_optimized_cm=182.0, completed=True)
        self.assertEqual(self._branch_value(), 182.0)

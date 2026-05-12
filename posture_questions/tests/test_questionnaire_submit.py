"""
HTTP-level tests for `POST /api/update-posture-questions` (`upsert_posture_questions`).

Run:
    pytest posture_questions/tests/test_questionnaire_submit.py -v
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from height_analysis.models import GeneticHeightEstimate
from posture_questions.models import PostureQuestion
from posture_questions.views import upsert_posture_questions
from user_profile.models import UserProfile
from users.models import PostureState

User = get_user_model()


def _mock_subscription_ok(user=None):
    return MagicMock(
        data={
            "expired": False,
            "days_left": 30,
            "plan": "Test",
            "plan_type": "Free",
            "is_paid": False,
            "is_trial": False,
            "message": "ok",
        }
    )


def _full_questionnaire_body():
    opts_a = '["A worst","B mid","C best"]'
    opts_q3 = '["Neck or upper back","Lower back","Hips or thighs","Hamstrings or calves","None"]'
    return {
        "forward_head_posture_question": "Q1",
        "forward_head_posture_options": opts_a,
        "forward_head_posture_answer": "A",
        "gap_between_your_lower_back_question": "Q2",
        "gap_between_your_lower_back_options": opts_a,
        "gap_between_your_lower_back_answer": "B",
        "tightness_or_discomfort_question": "Q3",
        "tightness_or_discomfort_options": opts_q3,
        "tightness_or_discomfort_answer": '["None"]',
        "slouch_when_standing_or_sitting_question": "Q4",
        "slouch_when_standing_or_sitting_options": opts_a,
        "slouch_when_standing_or_sitting_answer": "A",
        "feel_noticeably_shorter_end_of_day_compare_to_morning_question": "Q5",
        "feel_noticeably_shorter_end_of_day_compare_to_morning_options": opts_a,
        "feel_noticeably_shorter_end_of_day_compare_to_morning_answer": "B",
        "perfectly_aligned_and_decompressed_question": "Q6",
        "perfectly_aligned_and_decompressed_options": opts_a,
        "perfectly_aligned_and_decompressed_answer": "B",
        "flexible_in_your_hamstrings_and_hips_question": "Q7",
        "flexible_in_your_hamstrings_and_hips_options": opts_a,
        "flexible_in_your_hamstrings_and_hips_answer": "A",
        "active_your_core_during_daily_task_question": "Q8",
        "active_your_core_during_daily_task_options": opts_a,
        "active_your_core_during_daily_task_answer": "C",
    }


class QuestionnaireSubmitRequestMixin:
    def _factory_post(self, user, body: dict):
        from rest_framework.test import APIRequestFactory, force_authenticate

        factory = APIRequestFactory()
        request = factory.post("/api/update-posture-questions", body, format="json")
        force_authenticate(request, user=user)
        return request


@patch("posture_questions.views.apply_pending_pre_scan_engine1", lambda *a, **k: None)
@patch("posture_questions.views.RoutineService.ensure_active_routine", lambda *a, **k: None)
@patch("posture_questions.views.check_subscription_or_response", side_effect=_mock_subscription_ok)
class QuestionnaireSubmitTests(TestCase, QuestionnaireSubmitRequestMixin):
    def _create_user_with_profile(
        self,
        *,
        email_suffix: str,
        years_old: int,
        gender="male",
        father_cm=None,
        mother_cm=None,
        base_cm="175",
        skip_parents: bool = False,
    ):
        u = User.objects.create_user(
            username=f"qsub_{email_suffix}",
            email=f"qsub_{email_suffix}@test.example",
            password="secret123",
        )
        prof = UserProfile.objects.get(user=u)
        today = date.today()
        try:
            prof.birth_date = today.replace(year=today.year - years_old)
        except ValueError:
            prof.birth_date = today - timedelta(days=int(365.2425 * years_old))
        prof.gender = gender
        prof.base_height_cm = base_cm
        prof.current_height_cm = base_cm
        if not skip_parents:
            if father_cm is not None:
                prof.father_height_cm = str(father_cm)
            if mother_cm is not None:
                prof.mother_height_cm = str(mother_cm)
        prof.save()
        return User.objects.select_related("profile").get(pk=u.pk)

    def _call_upsert(self, user, body: dict):
        request = self._factory_post(user, body)
        return upsert_posture_questions(request)

    def test_unauthenticated_returns_401_or_403(self, _mock_sub):
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        request = factory.post("/api/update-posture-questions", {}, format="json")
        resp = upsert_posture_questions(request)
        self.assertIn(resp.status_code, (401, 403))

    def test_missing_userprofile_returns_server_error(self, _mock_sub):
        u = self._create_user_with_profile(email_suffix="prof_del", years_old=25)
        UserProfile.objects.filter(user=u).delete()
        u = User.objects.get(pk=u.pk)
        resp = self._call_upsert(u, _full_questionnaire_body())
        self.assertEqual(resp.status_code, 500)

    def test_invalid_age_string_returns_400(self, _mock_sub):
        u = self._create_user_with_profile(email_suffix="bad_age", years_old=25)
        prof = u.profile
        prof.age = "not-a-number"
        prof.birth_date = None
        prof.save()
        u = User.objects.select_related("profile").get(pk=u.pk)
        resp = self._call_upsert(u, _full_questionnaire_body())
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.data)

    def test_teen_missing_parent_height_returns_400(self, _mock_sub):
        u = self._create_user_with_profile(
            email_suffix="teen_nopar",
            years_old=15,
            father_cm=None,
            mother_cm=None,
            skip_parents=True,
        )
        resp = self._call_upsert(u, _full_questionnaire_body())
        self.assertEqual(resp.status_code, 400)

    def test_adult_full_submit_sets_questionnaire_completed(self, _mock_sub):
        u = self._create_user_with_profile(email_suffix="adult_ok", years_old=25)
        resp = self._call_upsert(u, _full_questionnaire_body())
        self.assertIn(resp.status_code, (200, 201))
        self.assertTrue(resp.data["user"]["questionnaire_completed"])
        self.assertIsNotNone(resp.data["user"].get("section3_contract"))
        st = PostureState.objects.get(user=u)
        self.assertTrue(st.questionnaire_completed)
        self.assertIsNotNone(st.questionnaire_completed_at)

    def test_adult_stamps_scan_unlock_fields(self, _mock_sub):
        u = self._create_user_with_profile(email_suffix="adult_scan", years_old=28)
        resp = self._call_upsert(u, _full_questionnaire_body())
        self.assertEqual(resp.status_code, 201)
        st = PostureState.objects.get(user=u)
        self.assertTrue(st.scan_completed)
        self.assertIsNotNone(st.last_scan_at)
        prof = u.profile
        prof.refresh_from_db()
        self.assertIsNotNone(prof.last_scan)

    def test_teen_full_submit_sets_questionnaire_completed(self, _mock_sub):
        u = self._create_user_with_profile(
            email_suffix="teen_ok",
            years_old=15,
            father_cm=182,
            mother_cm=165,
        )
        resp = self._call_upsert(u, _full_questionnaire_body())
        self.assertIn(resp.status_code, (200, 201))
        self.assertTrue(resp.data["user"]["questionnaire_completed"])
        st = PostureState.objects.get(user=u)
        self.assertTrue(st.questionnaire_completed)

    def test_teen_gender_none_with_parents_returns_server_error(self, _mock_sub):
        u = self._create_user_with_profile(
            email_suffix="teen_nogender",
            years_old=16,
            father_cm=180,
            mother_cm=165,
            gender=None,
        )
        resp = self._call_upsert(u, _full_questionnaire_body())
        self.assertEqual(resp.status_code, 500)

    def test_partial_answers_remain_incomplete(self, _mock_sub):
        u = self._create_user_with_profile(email_suffix="partial", years_old=25)
        body = _full_questionnaire_body()
        del body["active_your_core_during_daily_task_answer"]
        del body["active_your_core_during_daily_task_question"]
        del body["active_your_core_during_daily_task_options"]
        resp = self._call_upsert(u, body)
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(resp.data["user"]["questionnaire_completed"])
        st = PostureState.objects.get(user=u)
        self.assertFalse(st.questionnaire_completed)

    def test_whitespace_only_answer_incomplete(self, _mock_sub):
        u = self._create_user_with_profile(email_suffix="ws", years_old=25)
        body = _full_questionnaire_body()
        body["forward_head_posture_answer"] = "   "
        resp = self._call_upsert(u, body)
        self.assertFalse(resp.data["user"]["questionnaire_completed"])

    def test_unknown_fields_ignored_still_completes(self, _mock_sub):
        u = self._create_user_with_profile(email_suffix="extra_keys", years_old=25)
        body = _full_questionnaire_body()
        body["client_foo"] = "bar"
        resp = self._call_upsert(u, body)
        self.assertTrue(resp.data["user"]["questionnaire_completed"])

    def test_second_submit_returns_200_and_still_complete(self, _mock_sub):
        u = self._create_user_with_profile(email_suffix="twice", years_old=26)
        r1 = self._call_upsert(u, _full_questionnaire_body())
        self.assertEqual(r1.status_code, 201)
        r2 = self._call_upsert(u, _full_questionnaire_body())
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.data["user"]["questionnaire_completed"])


class Issue9VisualQuestionnaireScoringTests(TestCase):
    def test_issue9_example_matches_spec(self):
        from utils.posture.issue9_visual_scoring import compute_issue9_visual_results

        # Example scenario in doc: mostly B
        answers = {"q1": "B", "q2": "B", "q3": "B", "q4": "B", "q5": "A", "q6": "B", "q7": "A", "q8": "B"}
        r = compute_issue9_visual_results(answers)
        self.assertAlmostEqual(r["raw_loss_cm"], 3.7, places=2)
        self.assertAlmostEqual(r["total_loss_cm"], 3.7, places=2)
        self.assertAlmostEqual(r["total_recoverable_loss_cm"], 3.33, places=2)
        self.assertEqual(r["ranked_segments"][0], "collapse")
        self.assertEqual(r["ranked_segments"][1], "pelvic")

    def test_q8_is_multiplier_only(self):
        from utils.posture.issue9_visual_scoring import compute_issue9_visual_results

        base_answers = {"q1": "A", "q2": "A", "q3": "A", "q4": "A", "q5": "A", "q6": "A", "q7": "A"}
        r_a = compute_issue9_visual_results({**base_answers, "q8": "A"})
        r_d = compute_issue9_visual_results({**base_answers, "q8": "D"})
        # raw_loss should be identical (q8 not included)
        self.assertAlmostEqual(r_a["raw_loss_cm"], r_d["raw_loss_cm"], places=2)
        # recoverable must differ due to multiplier
        self.assertNotEqual(r_a["total_recoverable_loss_cm"], r_d["total_recoverable_loss_cm"])

    def test_q5_option_d_is_point6(self):
        from utils.posture.issue9_visual_scoring import compute_issue9_visual_results

        answers_b = {"q1": "A", "q2": "A", "q3": "A", "q4": "A", "q5": "B", "q6": "A", "q7": "A", "q8": "A"}
        answers_d = {**answers_b, "q5": "D"}
        r_b = compute_issue9_visual_results(answers_b)
        r_d = compute_issue9_visual_results(answers_d)
        # B and D are both 0.6, so totals match exactly when multiplier=1.0
        self.assertAlmostEqual(r_b["raw_loss_cm"], r_d["raw_loss_cm"], places=2)

    def test_issue9_can_use_existing_answer_fields_as_letters(self):
        """
        Ensures the legacy "update-posture-questions" payload can drive Issue9 scoring
        when answers are already letter-coded A-D.
        """
        from unittest.mock import MagicMock, patch
        from rest_framework.test import APIRequestFactory, force_authenticate
        from posture_questions.views import upsert_posture_questions
        from django.contrib.auth import get_user_model
        from user_profile.models import UserProfile
        from datetime import date, timedelta

        User = get_user_model()
        u = User.objects.create_user(username="issue9_letters", email="i9_letters@test.example", password="x")
        prof = UserProfile.objects.get(user=u)
        today = date.today()
        prof.birth_date = today - timedelta(days=int(365.2425 * 25))
        prof.base_height_cm = "175"
        prof.current_height_cm = "175"
        prof.gender = "male"
        prof.save()

        body = {
            "forward_head_posture_question": "Q1",
            "forward_head_posture_options": '["A","B","C","D"]',
            "forward_head_posture_answer": "B",
            "gap_between_your_lower_back_question": "Q2",
            "gap_between_your_lower_back_options": '["A","B","C","D"]',
            "gap_between_your_lower_back_answer": "B",
            "tightness_or_discomfort_question": "Q3",
            "tightness_or_discomfort_options": '["A","B","C","D"]',
            "tightness_or_discomfort_answer": "B",
            "slouch_when_standing_or_sitting_question": "Q4",
            "slouch_when_standing_or_sitting_options": '["A","B","C","D"]',
            "slouch_when_standing_or_sitting_answer": "B",
            "feel_noticeably_shorter_end_of_day_compare_to_morning_question": "Q5",
            "feel_noticeably_shorter_end_of_day_compare_to_morning_options": '["A","B","C","D"]',
            "feel_noticeably_shorter_end_of_day_compare_to_morning_answer": "A",
            "perfectly_aligned_and_decompressed_question": "Q6",
            "perfectly_aligned_and_decompressed_options": '["A","B","C","D"]',
            "perfectly_aligned_and_decompressed_answer": "B",
            "flexible_in_your_hamstrings_and_hips_question": "Q7",
            "flexible_in_your_hamstrings_and_hips_options": '["A","B","C","D"]',
            "flexible_in_your_hamstrings_and_hips_answer": "A",
            "active_your_core_during_daily_task_question": "Q8",
            "active_your_core_during_daily_task_options": '["A","B","C","D"]',
            "active_your_core_during_daily_task_answer": "B",
        }

        factory = APIRequestFactory()
        req = factory.post("/api/update-posture-questions", body, format="json")
        force_authenticate(req, user=u)

        with patch("posture_questions.views.check_subscription_or_response", return_value=MagicMock(data={"is_paid": False})):
            resp = upsert_posture_questions(req)

        self.assertIn(resp.status_code, (200, 201))
        self.assertEqual(resp.data["user"]["section3_contract"]["mode"], "issue9_visual")

    def test_teen_submit_creates_or_updates_genetic_estimate(self, _mock_sub):
        u = self._create_user_with_profile(
            email_suffix="teen_ge",
            years_old=14,
            father_cm=178,
            mother_cm=162,
        )
        self._call_upsert(u, _full_questionnaire_body())
        self.assertTrue(GeneticHeightEstimate.objects.filter(user=u).exists())

    def test_creates_posture_question_row(self, _mock_sub):
        u = self._create_user_with_profile(email_suffix="newrow", years_old=30)
        self.assertFalse(PostureQuestion.objects.filter(user=u).exists())
        self._call_upsert(u, _full_questionnaire_body())
        pq = PostureQuestion.objects.get(user=u)
        self.assertEqual(pq.forward_head_posture_answer, "A")

    def test_response_includes_subscription_data(self, _mock_sub):
        u = self._create_user_with_profile(email_suffix="subecho", years_old=27)
        resp = self._call_upsert(u, _full_questionnaire_body())
        self.assertIn("subscription_data", resp.data["user"])
        self.assertFalse(resp.data["user"]["subscription_data"]["is_paid"])

    def test_account_tier_adult_with_young_age_still_adult_track(self, _mock_sub):
        # Under 21 still requires parent heights for profile parsing; tier flags adult scoring path.
        u = self._create_user_with_profile(
            email_suffix="tier_adult",
            years_old=16,
            father_cm=182,
            mother_cm=165,
        )
        u.account_tier = "adult"
        u.save()
        resp = self._call_upsert(u, _full_questionnaire_body())
        self.assertIn(resp.status_code, (200, 201), msg=str(getattr(resp, "data", None)))
        contract = resp.data["user"].get("section3_contract") or {}
        self.assertIn("total_recoverable_loss_cm", contract)
        self.assertGreaterEqual(float(contract["total_recoverable_loss_cm"]), 1.0)


@patch("posture_questions.views.apply_pending_pre_scan_engine1", lambda *a, **k: None)
@patch("posture_questions.views.RoutineService.ensure_active_routine", lambda *a, **k: None)
@patch("posture_questions.views.check_subscription_or_response", side_effect=_mock_subscription_ok)
class QuestionnaireSubmitSmokeTests(TestCase, QuestionnaireSubmitRequestMixin):
    def test_smoke_matrix(self, _mock_sub):
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        r0 = upsert_posture_questions(factory.post("/api/update-posture-questions", {}, format="json"))
        self.assertIn(r0.status_code, (401, 403))

        u_a = User.objects.create_user(username="smoke_a", email="smoke_a@test.example", password="x")
        p_a = UserProfile.objects.get(user=u_a)
        p_a.birth_date = date.today() - timedelta(days=int(365.2425 * 30))
        p_a.gender = "female"
        p_a.base_height_cm = "170"
        p_a.current_height_cm = "170"
        p_a.save()
        u_a = User.objects.select_related("profile").get(pk=u_a.pk)
        ra = upsert_posture_questions(self._factory_post(u_a, _full_questionnaire_body()))
        self.assertTrue(ra.data["user"]["questionnaire_completed"])

        u_t = User.objects.create_user(username="smoke_t", email="smoke_t@test.example", password="x")
        p_t = UserProfile.objects.get(user=u_t)
        p_t.birth_date = date.today() - timedelta(days=int(365.2425 * 15))
        p_t.gender = "male"
        p_t.base_height_cm = "160"
        p_t.current_height_cm = "160"
        p_t.father_height_cm = "180"
        p_t.mother_height_cm = "165"
        p_t.save()
        u_t = User.objects.select_related("profile").get(pk=u_t.pk)
        rt = upsert_posture_questions(self._factory_post(u_t, _full_questionnaire_body()))
        self.assertTrue(rt.data["user"]["questionnaire_completed"])

        u_p = User.objects.create_user(username="smoke_p", email="smoke_p@test.example", password="x")
        p_p = UserProfile.objects.get(user=u_p)
        p_p.birth_date = date.today() - timedelta(days=int(365.2425 * 29))
        p_p.gender = "male"
        p_p.base_height_cm = "175"
        p_p.current_height_cm = "175"
        p_p.save()
        u_p = User.objects.select_related("profile").get(pk=u_p.pk)
        b = _full_questionnaire_body()
        del b["active_your_core_during_daily_task_answer"]
        del b["active_your_core_during_daily_task_question"]
        del b["active_your_core_during_daily_task_options"]
        rp = upsert_posture_questions(self._factory_post(u_p, b))
        self.assertFalse(rp.data["user"]["questionnaire_completed"])

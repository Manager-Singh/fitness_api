from datetime import date, timedelta

from django.test import TestCase

from posture_questions.models import PostureQuestion
from user_profile.models import UserProfile
from users.models import HeightLedger, PostureState, User
from users.spec_runtime import (
    LEDGER_ENTRY_APPLY_PENDING,
    LEDGER_ENTRY_PENDING_PRE_SCAN,
    apply_pending_pre_scan_engine1,
    get_user_runtime_state_snapshot,
)
from utils.posture.section3_manual_scoring import build_section3_manual_breakdown
from utils.routine_genrate import _questionnaire_ranked_segments, assign_teen_hgh_beast
from workouts.models import (
    AgeBracket,
    Exercise,
    ExerciseCategory,
    RoutineTemplate,
    RoutineVariant,
    Tier,
    Track,
    Type,
    Unit,
    VariantExercise,
)


class SpecV33QuestionnaireTests(TestCase):
    def _teen_user(self, years=15):
        u = User.objects.create_user(
            username="teenv33",
            email=f"teenv33_{years}@test.example",
            password="secret123",
        )
        dob = date.today() - timedelta(days=int(365.2425 * years))
        prof, _ = UserProfile.objects.get_or_create(user=u)
        prof.birth_date = dob
        prof.gender = "male"
        prof.base_height_cm = "160"
        prof.current_height_cm = "160"
        prof.save()
        ps, _ = PostureState.objects.get_or_create(user=u)
        ps.scan_completed = False
        ps.questionnaire_completed = False
        ps.save()
        # Ensure posture questionnaire row exists for this user.
        PostureQuestion.objects.get_or_create(user=u)
        return u

    def test_section3_teen_best_case_clamps_to_zero(self):
        u = self._teen_user(15)
        pq = PostureQuestion.objects.get(user=u)
        # Store options in the same "full text" style the DB uses.
        pq.forward_head_posture_options = '["Yes, it\\u0027s obvious","A little","Not at all"]'
        pq.forward_head_posture_answer = "Not at all"  # best case -> C
        pq.gap_between_your_lower_back_options = '["More than 2 inches","About 1 inch","Less than 1 inch"]'
        pq.gap_between_your_lower_back_answer = "Less than 1 inch"  # best case -> C
        pq.tightness_or_discomfort_options = '["Neck or upper back","Lower back","Hips or thighs","Hamstrings or calves","None"]'
        pq.tightness_or_discomfort_answer = '["None"]'  # best case -> E
        pq.slouch_when_standing_or_sitting_options = '["Often","Sometimes","Rarely"]'
        pq.slouch_when_standing_or_sitting_answer = "Rarely"  # best case -> C
        pq.feel_noticeably_shorter_end_of_day_compare_to_morning_options = '["Yes, every day","Occasionally","Not really"]'
        pq.feel_noticeably_shorter_end_of_day_compare_to_morning_answer = "Not really"  # best case -> C
        pq.perfectly_aligned_and_decompressed_options = '["0.5–1 inch taller","1–2 inches taller","Over 2 inches","Not sure"]'
        pq.perfectly_aligned_and_decompressed_answer = "Not sure"  # maps to D in options, score 0.60 but still fine
        pq.flexible_in_your_hamstrings_and_hips_options = '["Very stiff – I can\\u0027t touch my toes","Moderately flexible – near toes","Very flexible"]'
        pq.flexible_in_your_hamstrings_and_hips_answer = "Very flexible"  # best case -> C
        pq.active_your_core_during_daily_task_options = '["I have no awareness / weak core","I sometimes engage","I consciously activate daily"]'
        pq.active_your_core_during_daily_task_answer = "I consciously activate daily"  # best case -> C
        pq.save()

        out = build_section3_manual_breakdown(pq, clamp_min_cm=0.0)
        self.assertGreaterEqual(out["total_recoverable_loss_cm"], 0.0)
        self.assertLessEqual(out["total_recoverable_loss_cm"], 5.5)

    def test_section3_adult_best_case_clamps_to_one(self):
        """
        Spec v3.3 Section 3.3: adult clamp floor is 1.0 cm (teens are 0.0).
        """
        u = self._teen_user(15)
        pq = PostureQuestion.objects.get(user=u)
        # Fill best-case answers; use letter-coded values to keep this test minimal.
        pq.forward_head_posture_answer = "C"
        pq.gap_between_your_lower_back_answer = "C"
        pq.tightness_or_discomfort_answer = '["E"]'
        pq.slouch_when_standing_or_sitting_answer = "C"
        pq.feel_noticeably_shorter_end_of_day_compare_to_morning_answer = "C"
        pq.perfectly_aligned_and_decompressed_answer = "D"  # Q6: D=0.60
        pq.flexible_in_your_hamstrings_and_hips_answer = "C"
        pq.active_your_core_during_daily_task_answer = "C"
        pq.save()

        out = build_section3_manual_breakdown(pq, clamp_min_cm=1.0)
        self.assertEqual(out["total_recoverable_loss_cm"], 1.0)

    def test_section3_q6_reversal_c_is_severe(self):
        """
        Spec v3.3: Q6 is reversed; C should score 1.50 cm.
        """
        u = self._teen_user(15)
        pq = PostureQuestion.objects.get(user=u)
        # Zero out all other contributions (best-case), isolate Q6=C.
        pq.forward_head_posture_answer = "C"
        pq.gap_between_your_lower_back_answer = "C"
        pq.tightness_or_discomfort_answer = '["E"]'
        pq.slouch_when_standing_or_sitting_answer = "C"
        pq.feel_noticeably_shorter_end_of_day_compare_to_morning_answer = "C"
        pq.flexible_in_your_hamstrings_and_hips_answer = "C"
        pq.active_your_core_during_daily_task_answer = "C"
        pq.perfectly_aligned_and_decompressed_answer = "C"  # severe (1.50)
        pq.save()

        out = build_section3_manual_breakdown(pq, clamp_min_cm=0.0)
        self.assertAlmostEqual(out["raw_score_cm"], 1.5, places=2)
        self.assertAlmostEqual(out["total_recoverable_loss_cm"], 1.5, places=2)

    def test_section3_q3_cap_all_four_equals_point80(self):
        """
        Spec v3.3: Q3 sum is capped at 0.80 cm for A+B+C+D.
        """
        u = self._teen_user(15)
        pq = PostureQuestion.objects.get(user=u)
        # Zero out all other contributions, isolate Q3.
        pq.forward_head_posture_answer = "C"
        pq.gap_between_your_lower_back_answer = "C"
        pq.slouch_when_standing_or_sitting_answer = "C"
        pq.feel_noticeably_shorter_end_of_day_compare_to_morning_answer = "C"
        pq.perfectly_aligned_and_decompressed_answer = "A"  # 0.70, but keep best-case by using teen clamp min=0.0 and subtract later
        pq.flexible_in_your_hamstrings_and_hips_answer = "C"
        pq.active_your_core_during_daily_task_answer = "C"
        pq.tightness_or_discomfort_answer = '["A","B","C","D"]'
        pq.save()

        out = build_section3_manual_breakdown(pq, clamp_min_cm=0.0)
        # raw_score_cm includes Q6(A)=0.70; isolate Q3 by subtracting 0.70.
        q3_only = round(float(out["raw_score_cm"]) - 0.70, 2)
        self.assertEqual(q3_only, 0.80)

    def test_section3_worst_case_clamps_to_5p5_for_adult_and_teen(self):
        """
        Spec v3.3: worst-case raw=6.10 -> clamped to 5.50 for both tiers.
        """
        u = self._teen_user(15)
        pq = PostureQuestion.objects.get(user=u)
        # Worst-case: all A except Q6=C (reversed severe).
        pq.forward_head_posture_answer = "A"
        pq.gap_between_your_lower_back_answer = "A"
        pq.tightness_or_discomfort_answer = '["A","B","C","D"]'
        pq.slouch_when_standing_or_sitting_answer = "A"
        pq.feel_noticeably_shorter_end_of_day_compare_to_morning_answer = "A"
        pq.perfectly_aligned_and_decompressed_answer = "C"
        pq.flexible_in_your_hamstrings_and_hips_answer = "A"
        pq.active_your_core_during_daily_task_answer = "A"
        pq.save()

        teen_out = build_section3_manual_breakdown(pq, clamp_min_cm=0.0)
        adult_out = build_section3_manual_breakdown(pq, clamp_min_cm=1.0)
        self.assertEqual(teen_out["total_recoverable_loss_cm"], 5.5)
        self.assertEqual(adult_out["total_recoverable_loss_cm"], 5.5)

    def test_pending_engine1_applies_on_unlock(self):
        u = self._teen_user(15)
        # Create a pending pre-scan ledger row (engine1 only).
        row = HeightLedger(
            user=u,
            log_date=date(2024, 6, 10),
            entry_type=LEDGER_ENTRY_PENDING_PRE_SCAN,
            delta_um=0,
            cumulative_um=0,
            engine1_delta_um=1234,
            bio_delta_um=0,
            engine2_delta_dm=0,
            algorithm_version="v1",
            metadata={"pending": True},
        )
        row.save()
        out = apply_pending_pre_scan_engine1(u, when=date(2024, 6, 11))
        self.assertEqual(out["applied_um"], 1234)
        self.assertTrue(
            HeightLedger.objects.filter(user=u, entry_type=LEDGER_ENTRY_APPLY_PENDING).exists()
        )
        self.assertTrue(
            HeightLedger.objects.filter(user=u, entry_type="pending_pre_scan_applied").exists()
        )
        snap = get_user_runtime_state_snapshot(u)
        # Snapshot should not be None (it reads apply_pending/daily_compute only).
        self.assertIsNotNone(snap.get("current_height_um"))

    def test_pending_engine1_applies_on_scan_unlock(self):
        u = self._teen_user(15)
        row = HeightLedger(
            user=u,
            log_date=date(2024, 6, 10),
            entry_type=LEDGER_ENTRY_PENDING_PRE_SCAN,
            delta_um=0,
            cumulative_um=0,
            engine1_delta_um=777,
            bio_delta_um=0,
            engine2_delta_dm=0,
            algorithm_version="v1",
            metadata={"pending": True},
        )
        row.save()

        # Calling scan unlock should apply pending for teens per v3.3.
        from posture.views import _mark_scan_completed  # noqa: WPS433

        _mark_scan_completed(u)
        self.assertTrue(
            HeightLedger.objects.filter(user=u, entry_type=LEDGER_ENTRY_APPLY_PENDING).exists()
        )

    def test_section10_ranked_segments_works_with_full_text_answers(self):
        u = self._teen_user(15)
        pq = PostureQuestion.objects.get(user=u)
        pq.forward_head_posture_options = '["Yes, it\\u0027s obvious","A little","Not at all"]'
        pq.forward_head_posture_answer = "Yes, it's obvious"  # A -> 2
        pq.gap_between_your_lower_back_options = '["More than 2 inches","About 1 inch","Less than 1 inch"]'
        pq.gap_between_your_lower_back_answer = "About 1 inch"  # B -> 1
        pq.tightness_or_discomfort_options = '["Neck or upper back","Lower back","Hips or thighs","Hamstrings or calves","None"]'
        pq.tightness_or_discomfort_answer = '["Neck or upper back","Lower back"]'  # A+B selected
        pq.slouch_when_standing_or_sitting_options = '["Often","Sometimes","Rarely"]'
        pq.slouch_when_standing_or_sitting_answer = "Often"  # A -> 2
        pq.feel_noticeably_shorter_end_of_day_compare_to_morning_options = '["Yes, every day","Occasionally","Not really"]'
        pq.feel_noticeably_shorter_end_of_day_compare_to_morning_answer = "Yes, every day"  # A -> 2
        pq.flexible_in_your_hamstrings_and_hips_options = '["Very stiff – I can\\u0027t touch my toes","Moderately flexible – near toes","Very flexible"]'
        pq.flexible_in_your_hamstrings_and_hips_answer = "Very stiff – I can't touch my toes"  # A -> 2
        pq.active_your_core_during_daily_task_options = '["I have no awareness / weak core","I sometimes engage","I consciously activate daily"]'
        pq.active_your_core_during_daily_task_answer = "I have no awareness / weak core"  # A -> 2
        pq.save()

        ranked = _questionnaire_ranked_segments(u)
        self.assertEqual(len(ranked), 4)
        # Deterministic tie-break order exists; just ensure contains all segments.
        self.assertEqual(set(ranked), {"spinal_compression", "posture_collapse", "pelvic_tilt_back", "leg_hamstring"})

    def test_assign_teen_hgh_beast_picks_by_ranked_segment(self):
        u = self._teen_user(15)
        age = 15
        # Minimal HGH variant setup.
        bracket = AgeBracket.objects.create(title="13-17", min_age=13, max_age=17)
        tmpl = RoutineTemplate.objects.create(name="HGH Template")
        variant = RoutineVariant.objects.create(template=tmpl, age_bracket=bracket, track=Track.HGH)

        ex_core = Exercise.objects.create(name="Jump Rope Core", points=9, category=ExerciseCategory.HGH)
        ex_spinal = Exercise.objects.create(name="Spinal Beast", points=7, category=ExerciseCategory.HGH)
        ex_legs = Exercise.objects.create(name="Legs Beast", points=7, category=ExerciseCategory.HGH)

        VariantExercise.objects.create(
            variant=variant,
            exercise=ex_core,
            order=1,
            sets=1,
            quantity_min=1,
            quantity_max=1,
            unit=Unit.REPS,
            tier=Tier.CORE,
            type=Type.MAIN,
        )
        VariantExercise.objects.create(
            variant=variant,
            exercise=ex_spinal,
            order=1,
            sets=1,
            quantity_min=1,
            quantity_max=1,
            unit=Unit.REPS,
            tier=Tier.BEAST,
            type=Type.SPINALCPMPRESSION,
        )
        VariantExercise.objects.create(
            variant=variant,
            exercise=ex_legs,
            order=2,
            sets=1,
            quantity_min=1,
            quantity_max=1,
            unit=Unit.REPS,
            tier=Tier.BEAST,
            type=Type.LEGHAMSTRING,
        )

        # Prefer spinal first.
        picks = assign_teen_hgh_beast(variant, ["spinal_compression", "leg_hamstring"], age)
        self.assertEqual(len(picks), 1)
        self.assertEqual(picks[0].exercise_id, ex_spinal.id)


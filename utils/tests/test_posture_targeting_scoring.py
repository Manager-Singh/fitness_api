from django.test import SimpleTestCase

from utils.posture.issue9_visual_scoring import compute_issue9_visual_results


class PostureTargetingScoringTests(SimpleTestCase):
    def test_all_f_at_reference_height_hits_eight_cm_caps(self):
        result = compute_issue9_visual_results(
            {f"q{i}": "F" for i in range(1, 9)},
            height_cm=175,
            clamp_min_cm=1.0,
        )

        self.assertEqual(result["total_recoverable_loss_cm"], 8.0)
        self.assertEqual(result["segments"]["collapse"]["loss_cm"], 3.0)
        self.assertEqual(result["segments"]["spinal"]["loss_cm"], 2.5)
        self.assertEqual(result["segments"]["pelvic"]["loss_cm"], 1.5)
        self.assertEqual(result["segments"]["legs"]["loss_cm"], 1.0)

    def test_q8_feeds_spinal_and_pelvic_only(self):
        answers = {f"q{i}": "A" for i in range(1, 9)}
        answers["q8"] = "F"
        result = compute_issue9_visual_results(answers, height_cm=175, clamp_min_cm=0.0)

        self.assertEqual(result["segments"]["spinal"]["loss_cm"], 0.5)
        self.assertEqual(result["segments"]["pelvic"]["loss_cm"], 0.3)
        self.assertEqual(result["segments"]["collapse"]["loss_cm"], 0.0)
        self.assertEqual(result["segments"]["legs"]["loss_cm"], 0.0)

    def test_height_scaling_changes_cm_not_optimization_percent(self):
        answers = {f"q{i}": "F" for i in range(1, 9)}
        short = compute_issue9_visual_results(answers, height_cm=157, clamp_min_cm=0.0)
        tall = compute_issue9_visual_results(answers, height_cm=193, clamp_min_cm=0.0)

        self.assertEqual(short["total_recoverable_loss_cm"], 7.18)
        self.assertEqual(tall["total_recoverable_loss_cm"], 8.82)
        self.assertEqual(short["segments"]["collapse"]["opt_pct"], tall["segments"]["collapse"]["opt_pct"])

    def test_teen_all_a_has_zero_floor(self):
        result = compute_issue9_visual_results(
            {f"q{i}": "A" for i in range(1, 9)},
            height_cm=175,
            clamp_min_cm=0.0,
        )
        self.assertEqual(result["total_recoverable_loss_cm"], 0.0)

    def test_all_b_uses_organic_per_question_fractions(self):
        result = compute_issue9_visual_results(
            {f"q{i}": "B" for i in range(1, 9)},
            height_cm=175,
            clamp_min_cm=0.0,
        )

        self.assertEqual(round(result["segments"]["spinal"]["opt_pct"], 1), 82.9)
        self.assertEqual(round(result["segments"]["collapse"]["opt_pct"], 1), 83.1)
        self.assertEqual(round(result["segments"]["pelvic"]["opt_pct"], 1), 82.8)
        self.assertEqual(round(result["segments"]["legs"]["opt_pct"], 1), 83.5)
        self.assertEqual(len({
            round(result["segments"]["spinal"]["opt_pct"], 1),
            round(result["segments"]["collapse"]["opt_pct"], 1),
            round(result["segments"]["pelvic"]["opt_pct"], 1),
            round(result["segments"]["legs"]["opt_pct"], 1),
        }), 4)

    def test_all_a_and_all_f_are_hard_anchors(self):
        all_a = compute_issue9_visual_results(
            {f"q{i}": "A" for i in range(1, 9)},
            height_cm=175,
            clamp_min_cm=0.0,
        )
        all_f = compute_issue9_visual_results(
            {f"q{i}": "F" for i in range(1, 9)},
            height_cm=175,
            clamp_min_cm=0.0,
        )

        self.assertEqual(all_a["total_recoverable_loss_cm"], 0.0)
        self.assertTrue(all(seg["opt_pct"] == 100.0 for seg in all_a["segments"].values()))
        self.assertEqual(all_f["total_recoverable_loss_cm"], 8.0)
        self.assertTrue(all(seg["opt_pct"] == 0.0 for seg in all_f["segments"].values()))

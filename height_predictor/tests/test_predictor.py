"""
Unit tests for the pure Ultimate Height Predictor engine.

Covers the Part 8 worked examples and the Part 9 assertions. The worked examples in the spec
round intermediate values by hand, so we assert within a small tolerance (<= 0.2 cm) rather than
exact equality where that hand-rounding diverges from the continuous computation.
"""
from django.test import SimpleTestCase

from height_predictor.predictor import (
    PredictorInputs,
    predict_optimized_height,
)

TOL = 0.2


class WorkedExamplesTests(SimpleTestCase):
    def test_example_1_male_late_bloomer_band_a(self):
        r = predict_optimized_height(
            PredictorInputs(
                sex="male", age_years=14.5, current_height_cm=160,
                father_height_cm=180, mother_height_cm=166,
                voice_depth=1, facial_hair=1, body_hair=1, adams_apple=0,
            ),
            posture_recovery_cm=3.0,
        )
        self.assertEqual(r["band"], "A")
        self.assertAlmostEqual(r["true_optimized_cm"], 177.3, delta=TOL)

    def test_example_2_female_pre_menarche_band_a(self):
        r = predict_optimized_height(
            PredictorInputs(
                sex="female", age_years=13.0, current_height_cm=158,
                father_height_cm=178, mother_height_cm=170,
                menarche_status=0, body_hair=1,
            ),
            posture_recovery_cm=2.5,
        )
        self.assertEqual(r["band"], "A")
        # Spec hand-rounds to 171.5; continuous calc gives ~171.4.
        self.assertAlmostEqual(r["true_optimized_cm"], 171.5, delta=TOL)

    def test_example_3_male_band_b_grew_1cm(self):
        r = predict_optimized_height(
            PredictorInputs(
                sex="male", age_years=18.5, current_height_cm=177,
                father_height_cm=179, mother_height_cm=167,
                recent_growth_cm=1.0,
            ),
            posture_recovery_cm=4.0,
        )
        self.assertEqual(r["band"], "B")
        self.assertAlmostEqual(r["true_optimized_cm"], 181.6, delta=TOL)

    def test_example_4_female_band_b_floor_binds(self):
        r = predict_optimized_height(
            PredictorInputs(
                sex="female", age_years=17.6, current_height_cm=164,
                father_height_cm=175, mother_height_cm=162,
                menarche_status=3,
            ),
            posture_recovery_cm=2.0,
        )
        self.assertEqual(r["band"], "B")
        self.assertTrue(r["floor_applied"])
        self.assertAlmostEqual(r["true_optimized_cm"], 166.0, delta=TOL)


class SpecAssertionTests(SimpleTestCase):
    def _male(self, **kw):
        base = dict(
            sex="male", age_years=16.0, current_height_cm=168,
            father_height_cm=178, mother_height_cm=165,
        )
        base.update(kw)
        return PredictorInputs(**base)

    def test_late_bloomer_predicts_taller_than_early_maturer(self):
        # A 16-yo male with LOW maturity should predict taller than the same boy with HIGH maturity.
        low = predict_optimized_height(
            self._male(voice_depth=0, facial_hair=0, body_hair=0, adams_apple=0),
            posture_recovery_cm=3.0,
        )
        high = predict_optimized_height(
            self._male(voice_depth=2, facial_hair=2, body_hair=2, adams_apple=1),
            posture_recovery_cm=3.0,
        )
        self.assertGreater(low["true_optimized_cm"], high["true_optimized_cm"])

    def test_taller_current_height_predicts_taller(self):
        # Two 14-yo boys, same parents, different current height -> taller one predicts taller.
        short = predict_optimized_height(
            PredictorInputs(sex="male", age_years=14.0, current_height_cm=155,
                            father_height_cm=178, mother_height_cm=165, voice_depth=1),
            posture_recovery_cm=3.0,
        )
        tall = predict_optimized_height(
            PredictorInputs(sex="male", age_years=14.0, current_height_cm=170,
                            father_height_cm=178, mother_height_cm=165, voice_depth=1),
            posture_recovery_cm=3.0,
        )
        self.assertGreater(tall["true_optimized_cm"], short["true_optimized_cm"])

    def test_post_menarche_girl_near_current_plus_posture(self):
        # Menarche >2 yrs ago -> little growth left; prediction near current + posture.
        r = predict_optimized_height(
            PredictorInputs(sex="female", age_years=16.5, current_height_cm=165,
                            father_height_cm=170, mother_height_cm=162, menarche_status=3, body_hair=2),
            posture_recovery_cm=2.0,
        )
        self.assertLessEqual(abs(r["true_optimized_cm"] - (165 + 2.0)), 3.0)

    def test_no_tape_measure_still_returns_number(self):
        r = predict_optimized_height(
            PredictorInputs(sex="male", age_years=15.0, current_height_cm=165,
                            father_height_cm=178, mother_height_cm=165, voice_depth=1),
            posture_recovery_cm=3.0,
        )
        self.assertIsNotNone(r["true_optimized_cm"])
        self.assertEqual(r["frame_adj_cm"], 0.0)
        self.assertEqual(r["wing_adj_cm"], 0.0)

    def test_prediction_never_below_current_plus_posture(self):
        # Force a low genetic estimate (short parents, tall kid) -> floor must hold.
        r = predict_optimized_height(
            PredictorInputs(sex="male", age_years=17.0, current_height_cm=185,
                            father_height_cm=160, mother_height_cm=150,
                            voice_depth=2, facial_hair=2, body_hair=2, adams_apple=1),
            posture_recovery_cm=2.0,
        )
        self.assertGreaterEqual(r["true_optimized_cm"], 185 + 2.0)

    def test_band_b_dominated_by_current_height(self):
        # 18-yo prediction should be dominated by current height, not MPH.
        r = predict_optimized_height(
            PredictorInputs(sex="male", age_years=18.0, current_height_cm=180,
                            father_height_cm=165, mother_height_cm=158),
            posture_recovery_cm=0.0,
        )
        # With w_maturity ~0.83 at 18 and frac ~1.0, genetic potential hugs current height.
        self.assertLess(abs(r["true_optimized_cm"] - 180), 4.0)

    def test_tape_refinements_apply_when_provided(self):
        big_frame = predict_optimized_height(
            PredictorInputs(sex="male", age_years=15.0, current_height_cm=165,
                            father_height_cm=178, mother_height_cm=165, voice_depth=1,
                            wrist_circumference_cm=17.0, wingspan_cm=173.0),
            posture_recovery_cm=3.0,
        )
        self.assertEqual(big_frame["frame_adj_cm"], 0.8)   # ratio 165/17 = 9.7 < 10 -> large frame
        self.assertEqual(big_frame["wing_adj_cm"], 0.7)    # ape index 8 > 6

    def test_20_plus_is_posture_only(self):
        r = predict_optimized_height(
            PredictorInputs(sex="male", age_years=22.0, current_height_cm=175,
                            father_height_cm=180, mother_height_cm=165),
            posture_recovery_cm=3.0,
        )
        self.assertEqual(r["band"], "20+")
        self.assertAlmostEqual(r["true_optimized_cm"], 178.0, delta=0.05)

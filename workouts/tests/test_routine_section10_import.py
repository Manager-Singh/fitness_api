from django.test import SimpleTestCase


class RoutineSection10ImportTests(SimpleTestCase):
    def test_routine_helpers_importable(self):
        from utils.routine_genrate import (  # noqa: WPS433 — runtime import after Django setup
            _pick_exercises_for_tier_across_ranked,
            assign_adult_exercises,
            assign_teen_posture_exercises,
        )

        self.assertTrue(callable(_pick_exercises_for_tier_across_ranked))
        self.assertTrue(callable(assign_adult_exercises))
        self.assertTrue(callable(assign_teen_posture_exercises))

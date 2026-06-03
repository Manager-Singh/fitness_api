from django.test import SimpleTestCase


class RoutineSection10ImportTests(SimpleTestCase):
    def test_routine_helpers_importable(self):
        from utils.routine_genrate import (  # noqa: WPS433 — runtime import after Django setup
            assign_adult_exercises,
            assign_teen_hgh_beast,
            assign_teen_posture_exercises,
            build_posture_routine_slots,
        )

        self.assertTrue(callable(build_posture_routine_slots))
        self.assertTrue(callable(assign_adult_exercises))
        self.assertTrue(callable(assign_teen_posture_exercises))
        self.assertTrue(callable(assign_teen_hgh_beast))

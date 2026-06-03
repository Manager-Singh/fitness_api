from django.test import SimpleTestCase

from utils.routine_genrate import AGE_BASED_PROGRAM_TYPES


class Section10CountsV34Tests(SimpleTestCase):
    def test_teen_posture_assignment_is_10_exercises(self):
        # For all teen age bands defined in AGE_BASED_PROGRAM_TYPES, posture must be 10 total.
        for min_age, max_age, config in AGE_BASED_PROGRAM_TYPES:
            if min_age < 21:
                posture = (config or {}).get("POSTURE") or {}
                total = int(posture.get("core", 0) or 0) + int(posture.get("rec", 0) or 0) + int(posture.get("beast", 0) or 0)
                self.assertEqual(total, 10, f"Expected 10 posture exercises for {min_age}-{max_age}, got {total}")

    def test_adult_posture_assignment_is_10_exercises(self):
        # Adult config should also be 10 (6 core + 2 rec + 2 beast).
        for min_age, max_age, config in AGE_BASED_PROGRAM_TYPES:
            if min_age >= 21:
                posture = (config or {}).get("POSTURE") or {}
                total = int(posture.get("core", 0) or 0) + int(posture.get("rec", 0) or 0) + int(posture.get("beast", 0) or 0)
                self.assertEqual(total, 10)


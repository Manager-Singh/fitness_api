from django.test import TestCase

from workouts.exercise_spec_sheet_sync import exercise_fields_from_spec_row, run_sync
from workouts.exercise_spec_sheet_data import EXERCISE_SPEC_SHEET_ROWS
from workouts.models import Exercise


class ExerciseSpecSheetSyncTests(TestCase):
    def test_fields_single_method_three_steps(self):
        row = EXERCISE_SPEC_SHEET_ROWS["superman hold"]
        fields = exercise_fields_from_spec_row(row)
        self.assertEqual(len(fields["instruction_methods"]), 1)
        self.assertEqual(len(fields["instruction_steps"]), 3)
        self.assertIn("30 seconds", fields["instruction_methods"][0]["title"])

    def test_decompression_hang_safety_note(self):
        row = EXERCISE_SPEC_SHEET_ROWS["decompression hang"]
        fields = exercise_fields_from_spec_row(row)
        self.assertIn("solid wood", fields["safety_note"])

    def test_run_sync_updates_exercise(self):
        ex, _ = Exercise.objects.get_or_create(
            name="Superman Hold",
            defaults={"points": 7, "category": "posture"},
        )
        run_sync()
        ex.refresh_from_db()
        self.assertEqual(ex.description, EXERCISE_SPEC_SHEET_ROWS["superman hold"]["description"])
        self.assertEqual(len(ex.instruction_methods), 1)
        self.assertEqual(ex.instruction_steps, EXERCISE_SPEC_SHEET_ROWS["superman hold"]["steps"])

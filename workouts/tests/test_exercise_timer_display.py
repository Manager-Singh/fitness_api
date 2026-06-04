from django.test import SimpleTestCase

from workouts.exercise_timer_display import format_primary_timer_dosage, parse_primary_timer_dosage
from workouts.models import Unit


class ExerciseTimerDisplayTests(SimpleTestCase):
    def test_parse_rep_dosage(self):
        d = parse_primary_timer_dosage("2 set(s) × 20 reps")
        self.assertIsNotNone(d)
        self.assertEqual(d.sets, 2)
        self.assertEqual(d.quantity_min, 20)
        self.assertEqual(d.unit, Unit.REPS)
        self.assertFalse(d.is_timer)

    def test_parse_timer_per_side(self):
        d = parse_primary_timer_dosage("2 set(s) × 30 seconds per side (timer)")
        self.assertIsNotNone(d)
        self.assertEqual(d.unit, Unit.SECS)
        self.assertTrue(d.is_timer)
        self.assertTrue(d.per_side)

    def test_format_round_trip(self):
        text = format_primary_timer_dosage(
            sets=2, quantity_min=45, quantity_max=None, unit=Unit.SECS, per_side=False
        )
        self.assertIn("(timer)", text)
        parsed = parse_primary_timer_dosage(text)
        self.assertEqual(parsed.quantity_min, 45)

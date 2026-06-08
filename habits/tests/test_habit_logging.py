from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from habits.models import MicroHabit
from habits.services import (
    capped_habit_points_for_engine,
    log_habit,
    total_raw_habit_points,
    DAILY_HABIT_CAP,
)

User = get_user_model()


class HabitLoggingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="habit_user", password="x", email="h@t.com")
        self.log_date = date(2026, 5, 19)

    def test_seed_habits_exist(self):
        self.assertEqual(MicroHabit.objects.filter(is_active=True).count(), 4)

    def test_toggle_same_slot_removes_entry(self):
        log_habit(self.user, self.log_date, "puppet_string_walk", "am")
        entry, action = log_habit(self.user, self.log_date, "puppet_string_walk", "am")
        self.assertIsNone(entry)
        self.assertEqual(action, "removed")
        self.assertEqual(total_raw_habit_points(self.user, self.log_date), 0)

    def test_toggle_log_again_after_remove(self):
        # Part 3: Tech Neck Lift is now 2 pts (once/day).
        log_habit(self.user, self.log_date, "tech_neck_lift", "once")
        log_habit(self.user, self.log_date, "tech_neck_lift", "once")
        entry, action = log_habit(self.user, self.log_date, "tech_neck_lift", "once")
        self.assertEqual(action, "created")
        self.assertEqual(entry.points, 2)
        self.assertEqual(total_raw_habit_points(self.user, self.log_date), 2)

    def test_puppet_am_pm_two_slots_six_points(self):
        # Part 3: Puppet String Walk is 3 pts per slot → 6 across AM + PM.
        log_habit(self.user, self.log_date, "puppet_string_walk", "am")
        log_habit(self.user, self.log_date, "puppet_string_walk", "pm")
        self.assertEqual(total_raw_habit_points(self.user, self.log_date), 6)

    def test_daily_cap_twelve(self):
        self.assertEqual(DAILY_HABIT_CAP, 12)
        # All AM/PM habits + the once/day Tech Neck Lift → exactly 12.
        for code in ("puppet_string_walk", "desk_un_slouch", "doorway_posture_reset"):
            log_habit(self.user, self.log_date, code, "am")
            log_habit(self.user, self.log_date, code, "pm")
        log_habit(self.user, self.log_date, "tech_neck_lift", "once")
        self.assertEqual(total_raw_habit_points(self.user, self.log_date), 12)
        self.assertEqual(capped_habit_points_for_engine(self.user, self.log_date), DAILY_HABIT_CAP)

    def test_rebuild_ledger_includes_habit_only_day(self):
        from users.models import DailyLog
        from users.spec_runtime import rebuild_ledger_from_date

        log_habit(self.user, self.log_date, "tech_neck_lift", "once")
        rebuild_ledger_from_date(self.user, self.log_date)
        daily = DailyLog.objects.filter(user=self.user, log_date=self.log_date).first()
        self.assertIsNotNone(daily)
        self.assertEqual(daily.habit_points, 2)
        self.assertGreaterEqual(daily.engine1_points, 2)


class HabitLogTimeEnforcementTests(TestCase):
    """Part 7.4 — per-habit and global daily caps enforced at POST/log time."""

    def setUp(self):
        self.user = User.objects.create_user(username="habit_cap_user", password="x", email="hc@t.com")
        self.log_date = date(2026, 5, 19)

    def test_per_habit_daily_max_rejected_at_log_time(self):
        from django.core.exceptions import ValidationError

        habit = MicroHabit.objects.create(
            code="cap_test_ampm",
            name="Cap Test",
            logging_mode=MicroHabit.AM_PM,
            points_per_log=2,
            daily_max_points=2,  # AM already maxes it; PM must be rejected.
            sort_order=99,
        )
        log_habit(self.user, self.log_date, habit.code, "am")
        with self.assertRaises(ValidationError):
            log_habit(self.user, self.log_date, habit.code, "pm")
        self.assertEqual(total_raw_habit_points(self.user, self.log_date), 2)

    def test_global_daily_cap_rejected_at_log_time(self):
        from django.core.exceptions import ValidationError

        habit = MicroHabit.objects.create(
            code="cap_test_big",
            name="Big Cap Test",
            logging_mode=MicroHabit.ONCE_DAILY,
            points_per_log=20,
            daily_max_points=20,  # per-habit OK, but exceeds global DAILY_HABIT_CAP (12).
            sort_order=98,
        )
        with self.assertRaises(ValidationError):
            log_habit(self.user, self.log_date, habit.code, "once")
        self.assertEqual(total_raw_habit_points(self.user, self.log_date), 0)

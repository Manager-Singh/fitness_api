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

    def test_am_pm_upsert_same_slot(self):
        log_habit(self.user, self.log_date, "puppet_string_walk", "am")
        entry, created = log_habit(self.user, self.log_date, "puppet_string_walk", "am")
        self.assertFalse(created)
        self.assertEqual(entry.points, 1)

    def test_am_pm_two_slots_two_points(self):
        log_habit(self.user, self.log_date, "puppet_string_walk", "am")
        log_habit(self.user, self.log_date, "puppet_string_walk", "pm")
        self.assertEqual(total_raw_habit_points(self.user, self.log_date), 2)

    def test_daily_cap_six(self):
        for code in ("puppet_string_walk", "desk_un_slouch"):
            log_habit(self.user, self.log_date, code, "am")
            log_habit(self.user, self.log_date, code, "pm")
        log_habit(self.user, self.log_date, "tech_neck_lift", "once")
        log_habit(self.user, self.log_date, "doorway_posture_reset", "once")
        self.assertEqual(total_raw_habit_points(self.user, self.log_date), 6)
        self.assertEqual(capped_habit_points_for_engine(self.user, self.log_date), DAILY_HABIT_CAP)

    def test_rebuild_ledger_includes_habit_only_day(self):
        from users.models import DailyLog
        from users.spec_runtime import rebuild_ledger_from_date

        log_habit(self.user, self.log_date, "tech_neck_lift", "once")
        rebuild_ledger_from_date(self.user, self.log_date)
        daily = DailyLog.objects.filter(user=self.user, log_date=self.log_date).first()
        self.assertIsNotNone(daily)
        self.assertEqual(daily.habit_points, 1)
        self.assertGreaterEqual(daily.engine1_points, 1)

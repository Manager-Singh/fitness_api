from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class MicroHabit(models.Model):
    AM_PM = "am_pm"
    ONCE_DAILY = "once_daily"
    LOGGING_MODES = [
        (AM_PM, "AM and PM (1 pt each)"),
        (ONCE_DAILY, "Once per day"),
    ]

    code = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=160)
    ui_prompt = models.TextField(blank=True)
    daily_max_points = models.PositiveSmallIntegerField(default=1)
    logging_mode = models.CharField(max_length=16, choices=LOGGING_MODES, default=ONCE_DAILY)
    points_per_log = models.PositiveSmallIntegerField(default=1)
    sort_order = models.PositiveSmallIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("sort_order", "name")

    def __str__(self):
        return self.name


class MicroHabitLog(models.Model):
    SLOT_AM = "am"
    SLOT_PM = "pm"
    SLOT_ONCE = "once"
    SLOT_CHOICES = [
        (SLOT_AM, "AM"),
        (SLOT_PM, "PM"),
        (SLOT_ONCE, "Once"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="micro_habit_logs",
    )
    log_date = models.DateField(db_index=True)
    habit = models.ForeignKey(
        MicroHabit,
        on_delete=models.PROTECT,
        related_name="logs",
    )
    slot = models.CharField(max_length=8, choices=SLOT_CHOICES)
    points = models.PositiveSmallIntegerField(default=1)
    logged_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-logged_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["user", "log_date", "habit", "slot"],
                name="unique_micro_habit_log_per_slot",
            ),
        ]

    def clean(self):
        mode = self.habit.logging_mode if self.habit_id else None
        if mode == MicroHabit.AM_PM and self.slot not in (self.SLOT_AM, self.SLOT_PM):
            raise ValidationError({"slot": "AM/PM habits require slot 'am' or 'pm'."})
        if mode == MicroHabit.ONCE_DAILY and self.slot != self.SLOT_ONCE:
            raise ValidationError({"slot": "Once-daily habits require slot 'once'."})

    def save(self, *args, **kwargs):
        if self.habit_id and not self.points:
            self.points = int(self.habit.points_per_log or 1)
        self.full_clean()
        super().save(*args, **kwargs)

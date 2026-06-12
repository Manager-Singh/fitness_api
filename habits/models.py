from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


def validate_instruction_steps(value):
    """instruction_steps must be a JSON array of strings."""
    if value in (None, ""):
        return
    if not isinstance(value, list):
        raise ValidationError("Instruction steps must be a JSON array.")
    for i, item in enumerate(value):
        if item is not None and not isinstance(item, str):
            raise ValidationError(f"Step {i + 1} must be a string.")


class MicroHabit(models.Model):
    AM_PM = "am_pm"
    ONCE_DAILY = "once_daily"
    LOGGING_MODES = [
        (AM_PM, "AM and PM"),
        (ONCE_DAILY, "Once per day"),
    ]

    code = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=160)
    ui_prompt = models.TextField(blank=True)
    how_to_detail = models.TextField(
        blank=True,
        help_text="Expanded 'How to' panel copy for the habits screen (Friday Task 5).",
    )
    instruction_steps = models.JSONField(
        default=list,
        blank=True,
        validators=[validate_instruction_steps],
        verbose_name="Instruction steps",
        help_text="Ordered steps for the app. In admin, use one box per step (Add more / Remove).",
    )
    image = models.ImageField(upload_to="micro_habits/", blank=True, null=True)
    daily_max_points = models.PositiveSmallIntegerField(default=1)
    logging_mode = models.CharField(max_length=16, choices=LOGGING_MODES, default=ONCE_DAILY)
    points_per_log = models.PositiveSmallIntegerField(default=1)
    sort_order = models.PositiveSmallIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("sort_order", "name")

    def __str__(self):
        return self.name

    def get_instruction_steps(self) -> list[str]:
        """Ordered step strings for API (prefers instruction_steps JSON)."""
        steps = self.instruction_steps
        if isinstance(steps, list) and steps:
            return [str(s).strip() for s in steps if str(s).strip()]
        text = (self.how_to_detail or self.ui_prompt or "").strip()
        if not text:
            return []
        parts = [p.strip() for p in text.split("\n\n") if p.strip()]
        return parts if parts else [text]

    def get_instruction_lines(self) -> list[str]:
        """Alias for app clients that use the exercise-style key name."""
        return self.get_instruction_steps()


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

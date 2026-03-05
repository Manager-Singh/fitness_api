from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Module, Food, Activity       # core tables


class NutraSession(models.Model):
    """
    One daily record per user.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,
                             related_name="nutra_sessions")
    date = models.DateField(default=timezone.localdate)

    class Meta:
        unique_together = ("user", "date")
        ordering = ("-date",)

    def __str__(self):
        return f"{self.user} · {self.date}"


class NutraEntry(models.Model):
    """
    A consumed food OR completed lifestyle habit.
    Exactly one of (food, activity) is set.
    """
    session  = models.ForeignKey(NutraSession,
                                 on_delete=models.CASCADE,
                                 related_name="entries")
    module   = models.ForeignKey(Module, on_delete=models.PROTECT)

    food     = models.ForeignKey(Food, null=True, blank=True,
                                 on_delete=models.PROTECT,
                                 related_name="nutra_entries")
    activity = models.ForeignKey(Activity, null=True, blank=True,
                                 on_delete=models.PROTECT,
                                 related_name="nutra_entries")

    servings = models.CharField(max_length=120, blank=True)
    score    = models.PositiveSmallIntegerField(null=True, blank=True)  # ← stores points
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-completed_at",)

    # ----------------------- validation ----------------------
    def clean(self):
        if bool(self.food) == bool(self.activity):
            raise ValidationError("Specify either food or activity, not both.")

    # --------------------- auto-fill score -------------------
    def save(self, *args, **kwargs):
        if self.score is None:
            if self.food:
                rel = self.module.module_foods.filter(food=self.food).first()
                self.score = rel.score if rel else 0
            elif self.activity:
                rel = self.module.module_activities.filter(activity=self.activity).first()
                self.score = rel.score if rel else 0
            else:
                self.score = 0
        super().save(*args, **kwargs)

    def __str__(self):
        item = self.food or self.activity
        return f"{self.session} – {item}"

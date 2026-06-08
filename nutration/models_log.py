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
                if rel:
                    from nutration.scoring import module_food_score_for_user

                    self.score = module_food_score_for_user(rel, self.session.user)
                else:
                    self.score = 0
            elif self.activity:
                rel = self.module.module_activities.filter(activity=self.activity).first()
                self.score = rel.score if rel else 0
            else:
                self.score = 0
        super().save(*args, **kwargs)

    def __str__(self):
        item = self.food or self.activity
        return f"{self.session} – {item}"


class AdultNutritionDay(models.Model):
    """
    Part 2 — adult (21+) nutrition redesign. One server-authoritative row per user per
    local day capturing measurable protein + hydration (replaces the old 13-food list).

    Scoring (see utils/adult_nutrition):
        protein_points   = min(9, protein_grams // 10)
        hydration_points = min(6, water_500ml + 2 * spine_500ml)
        nutrition_points = min(15, protein_points + hydration_points)
    Spine drinks are worth double on purpose (electrolytes/collagen for spinal discs).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="adult_nutrition_days",
    )
    log_date = models.DateField(db_index=True)
    protein_grams = models.PositiveIntegerField(default=0)
    water_ml = models.PositiveIntegerField(default=0)
    # Number of 500 ml spine-drink servings logged today (each worth 2 hydration pts).
    spine_500ml_count = models.PositiveIntegerField(default=0)
    # Optional per-type breakdown, e.g. [{"type": "bone_broth", "count": 2}].
    spine_drinks = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "log_date")
        ordering = ("-log_date",)

    def __str__(self):
        return f"AdultNutritionDay({self.user_id} · {self.log_date})"

from django.db import models
from django.core.validators import MinValueValidator
from django.db.models.signals import pre_save
from django.dispatch import receiver


# ─────────── core buckets ───────────
class AgeGroup(models.Model):
    name     = models.CharField(max_length=40, unique=True)
    min_age  = models.PositiveSmallIntegerField()
    max_age  = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ("min_age",)

    def __str__(self):
        return self.name


# class Module(models.Model):
#     NUTRITION, LIFESTYLE = "NUT", "LIFE"
#     MODULE_TYPES = [
#         (NUTRITION, "Nutrition"),
#         (LIFESTYLE, "Lifestyle"),
#     ]

#     name      = models.CharField(max_length=160)
#     type      = models.CharField(max_length=4, choices=MODULE_TYPES)
#     age_group = models.ForeignKey(
#         AgeGroup, on_delete=models.CASCADE, related_name="modules"
#     )

#     class Meta:
#         unique_together = ("name", "age_group")
#         ordering        = ("age_group__min_age", "type", "name")

#     def __str__(self):
#         return f"{self.name} ({self.age_group})"

class Module(models.Model):
    NUTRITION, LIFESTYLE = "NUT", "LIFE"
    MODULE_TYPES = [
        (NUTRITION, "Nutrition"),
        (LIFESTYLE, "Lifestyle"),
    ]

    name      = models.CharField(max_length=160)
    short_name = models.CharField(
        max_length=80,
        blank=True,
        help_text="Short display name (e.g. Protein Boost)"
    )

    type      = models.CharField(max_length=4, choices=MODULE_TYPES)
    age_group = models.ForeignKey(
        AgeGroup, on_delete=models.CASCADE, related_name="modules"
    )

    # 🆕 UI / Content fields
    icon_image = models.ImageField(
        upload_to="modules/icons/",
        blank=True,
        null=True
    )
    background_image = models.ImageField(
        upload_to="modules/backgrounds/",
        blank=True,
        null=True
    )
    action_btn = models.CharField(
        max_length=80,
        blank=True,
        help_text="CTA text (e.g. Start, Explore, Track)"
    )
    tag_line = models.CharField(
        max_length=160,
        blank=True,
        help_text="Short motivational line"
    )

    class Meta:
        unique_together = ("name", "age_group")
        ordering = ("age_group__min_age", "type", "name")

    def __str__(self):
        return f"{self.name} ({self.age_group})"


# ─────────── nutrition side ───────────
class Food(models.Model):
    name        = models.CharField(max_length=160, unique=True)
    short_name  = models.CharField(max_length=160, blank=True)
    calories    = models.PositiveSmallIntegerField(null=True, blank=True)
    protein     = models.DecimalField(max_digits=6, decimal_places=2,
                                      null=True, blank=True)
    image       = models.ImageField(upload_to="foods/", blank=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class ModuleFood(models.Model):
    module        = models.ForeignKey(
        Module, on_delete=models.CASCADE, related_name="module_foods"
    )
    food          = models.ForeignKey(
        Food, on_delete=models.CASCADE, related_name="module_foods"
    )
    score         = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    serving_size  = models.CharField(max_length=120, blank=True)
    details       = models.TextField(blank=True)

    class Meta:
        unique_together = ("module", "food")
        ordering        = ("-score", "food__name")

    def __str__(self):
        return f"{self.food} – {self.module}"


# ─────────── lifestyle side ───────────
class Activity(models.Model):
    name             = models.CharField(max_length=160, unique=True)
    short_name       = models.CharField(max_length=160, blank=True)
    default_duration = models.CharField(max_length=40, blank=True)
    image            = models.ImageField(upload_to="activities/", blank=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class ModuleActivity(models.Model):
    module = models.ForeignKey(
        
        Module, on_delete=models.CASCADE, related_name="module_activities"
    )
    activity = models.ForeignKey(
        Activity, on_delete=models.CASCADE, related_name="module_activities"
    )

    score          = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    recommendation = models.CharField(max_length=120, blank=True)
    details        = models.TextField(blank=True)

    # ──────── NEW MEDIA FIELDS ────────
    audio = models.FileField(
        upload_to="module_activities/audio/",
        blank=True,
        null=True
    )
    video = models.FileField(
        upload_to="module_activities/video/",
        blank=True,
        null=True
    )

    class Meta:
        unique_together = ("module", "activity")
        ordering        = ("-score", "activity__name")

    def __str__(self):
        return f"{self.activity} – {self.module}"


# ─────────── auto-purge mismatched children ───────────
@receiver(pre_save, sender=Module)
def _purge_invalid_children(sender, instance, **_):
    if not instance.pk:
        return

    prev = sender.objects.only("type").get(pk=instance.pk)

    # same type → no cleanup
    if prev.type == instance.type:
        return

    # switching to NUTRITION → delete all activities
    if instance.type == Module.NUTRITION:
        instance.module_activities.all().delete()
    else:
        # switching to LIFESTYLE → delete all foods
        instance.module_foods.all().delete()

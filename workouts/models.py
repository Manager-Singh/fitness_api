# workouts/models.py
from django.core.exceptions import ValidationError
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.conf import settings


def validate_instruction_steps(value):
    """instruction_steps must be a JSON array of strings (any length)."""
    if value in (None, "", []):
        return
    if not isinstance(value, list):
        raise ValidationError("Must be a JSON array, e.g. [\"#1. ...\", \"#2. ...\"].")
    for i, item in enumerate(value):
        if not isinstance(item, str):
            raise ValidationError(f"Item {i + 1}: must be a string.")
        if len(item) > 2000:
            raise ValidationError(f"Item {i + 1}: is too long (max 2000 characters).")


def validate_instruction_methods(value):
    """
    instruction_methods must be a JSON array of objects:
    [
      {"title": "Method A ...", "steps": ["...", "..."]},
      {"title": "Method B ...", "steps": ["...", "..."]},
    ]
    """
    if value in (None, "", []):
        return
    if not isinstance(value, list):
        raise ValidationError('Must be a JSON array, e.g. [{"title": "...", "steps": ["#1...", "#2..."]}].')
    for i, m in enumerate(value):
        if not isinstance(m, dict):
            raise ValidationError(f"Method {i + 1} must be an object.")
        title = m.get("title", "")
        steps = m.get("steps", [])
        if title is None:
            title = ""
        if not isinstance(title, str):
            raise ValidationError(f"Method {i + 1} title must be a string.")
        if len(title) > 200:
            raise ValidationError(f"Method {i + 1} title is too long (max 200 characters).")
        if steps in (None, ""):
            steps = []
        if not isinstance(steps, list):
            raise ValidationError(f"Method {i + 1} steps must be a list.")
        for j, s in enumerate(steps):
            if not isinstance(s, str):
                raise ValidationError(f"Method {i + 1} step {j + 1} must be a string.")
            if len(s) > 2000:
                raise ValidationError(f"Method {i + 1} step {j + 1} is too long (max 2000 characters).")


# ──────────────────── Exercise metadata ────────────────────
class ExerciseCategory(models.TextChoices):
    POSTURE      = "posture",      "Posture"
    ENVIRONMENT  = "environment",  "Environment"
    HGH          = "hgh",          "HGH / Sprint"
    GENERAL      = "general",      "General"


class Exercise(models.Model):
    name        = models.CharField(max_length=120, unique=True)
    short_name       = models.CharField(blank=True, max_length=160)
    description = models.TextField(blank=True)
    instruction_content = models.TextField(
        blank=True,
        verbose_name="Instruction content (plain text)",
        help_text=(
            "Optional legacy format: multiple lines in one box (title + dosage, then #1, #2, …). "
            "If “Instruction steps (JSON array)” is set, the API prefers that over this field."
        ),
    )
    instruction_steps = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Instructions (steps)",
        help_text=(
            "Optional ordered list of lines for the app. In admin, use one text box per step "
            "(Add more / Remove). Stored as JSON in the database."
        ),
        validators=[validate_instruction_steps],
    )
    instruction_methods = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Instructions (methods)",
        help_text=(
            "Optional structured instruction methods (each method has a title and ordered steps). "
            "If set, the app can show Method A/Method B selectors. Stored as JSON."
        ),
        validators=[validate_instruction_methods],
    )
    safety_note = models.TextField(
        blank=True,
        verbose_name="Safety note",
        help_text="Optional safety note shown under the instructions (plain text).",
    )
    points      = models.PositiveIntegerField(default=0)
    category    = models.CharField(                   # NEW
        max_length=12,
        choices=ExerciseCategory.choices,
        default=ExerciseCategory.GENERAL,
    )
    photo       = models.ImageField(upload_to="exercises/", blank=True, null=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_instruction_lines(self):
        """
        Ordered lines for the app: prefer JSON array; else split legacy instruction_content.
        """
        methods = self.instruction_methods
        if isinstance(methods, list) and len(methods) > 0:
            out = []
            for m in methods:
                if not isinstance(m, dict):
                    continue
                title = str(m.get("title") or "").strip()
                steps = m.get("steps") or []
                if title:
                    out.append(title)
                if isinstance(steps, list):
                    for s in steps:
                        s2 = str(s).strip()
                        if s2:
                            out.append(s2)
            if out:
                return out
        steps = self.instruction_steps
        if isinstance(steps, list) and len(steps) > 0:
            return [str(s).strip() for s in steps if str(s).strip()]
        text = (self.instruction_content or "").strip()
        if not text:
            return []
        return [ln.strip() for ln in text.splitlines() if ln.strip()]

    def get_instruction_methods(self):
        """
        Normalized structured methods for the app.
        Returns: [{"title": str, "steps": [str, ...]}, ...]
        """
        methods = self.instruction_methods
        if not isinstance(methods, list):
            return []
        out = []
        for m in methods:
            if not isinstance(m, dict):
                continue
            title = str(m.get("title") or "").strip()
            steps = m.get("steps") if isinstance(m.get("steps"), list) else []
            steps2 = [str(s).strip() for s in steps if str(s).strip()]
            if title or steps2:
                out.append({"title": title, "steps": steps2})
        return out


# ──────────────────── Variant-level metadata ────────────────────
class Track(models.TextChoices):
    ESSENTIALS   = "ess", "Essentials"
    POSTURE      = "pos", "Posture"
    HGH          = "hgh", "HGH"
    # ENVIRONMENT  = "env", "Environment"


class Tier(models.TextChoices):
    CORE         = "core",  "Core"
    RECOMMENDED  = "rec",   "Recommended"
    BEAST        = "beast", "Beast mode"
    
class Type(models.TextChoices):
    MAIN         = "main",  "Main"
    SPINALCPMPRESSION = "spinal_compression",   "Spinal Compression"
    POSTURALCOLLAPSE = "postural_collapse",   "Postural Collapse"
    PELCIVTILTBACK = "pelvic_tilt_back",   "Pelvic Tilt & Back"
    LEGHAMSTRING = "leg_hamstring",   "Leg & Hamstring"


class AgeBracket(models.Model):
    title   = models.CharField(max_length=40)        # “14–17”, “60+”, …
    min_age = models.PositiveSmallIntegerField()
    max_age = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["min_age"]

    def __str__(self):
        return f"{self.min_age}+" if self.max_age is None else f"{self.min_age}–{self.max_age}"


# ───────────────────  template / variant split  ───────────────────

class RoutineTemplate(models.Model):
    """
    A *named* programme, independent of age.
    e.g. “Core 6 – HeightMax Essentials”
    """
    name  = models.CharField(max_length=120, unique=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

class RoutineVariant(models.Model):
    template    = models.ForeignKey(RoutineTemplate, on_delete=models.CASCADE,
                                    related_name="variants")
    age_bracket = models.ForeignKey(AgeBracket, on_delete=models.PROTECT,
                                    related_name="routine_variants")
    track       = models.CharField(max_length=3, choices=Track.choices,
                                   default=Track.ESSENTIALS)      # NEW
    notes       = models.TextField(blank=True)

    class Meta:
        unique_together = [("template", "age_bracket", "track")]
        ordering        = ["template__name", "age_bracket__min_age"]

    def __str__(self):
        return f"{self.template} / {self.track} ({self.age_bracket})"


class Unit(models.TextChoices):
    REPS  = "reps", "Reps"
    SECS  = "secs", "Seconds"


class VariantExercise(models.Model):
    variant       = models.ForeignKey(RoutineVariant, on_delete=models.CASCADE,
                                      related_name="prescriptions")
    exercise      = models.ForeignKey(Exercise, on_delete=models.PROTECT)
    order         = models.PositiveSmallIntegerField()
    sets          = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    quantity_min  = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    quantity_max  = models.PositiveSmallIntegerField(null=True, blank=True)
    unit          = models.CharField(max_length=8, choices=Unit.choices,
                                     default=Unit.REPS)
    tier          = models.CharField(max_length=5, choices=Tier.choices,
                                     default=Tier.CORE)           # NEW
    type          = models.CharField(max_length=25, choices=Type.choices,
                                     default=Type.MAIN)           # NEW
       # ✅ NEW: gender-specific images
    image_male    = models.ImageField(
        upload_to="variant_exercises/male/",
        null=True,
        blank=True
    )
    image_female  = models.ImageField(
        upload_to="variant_exercises/female/",
        null=True,
        blank=True
    )

    notes         = models.CharField(max_length=120, blank=True)

    class Meta:
        unique_together = [("variant", "exercise")]
        ordering        = ["variant", "order"]

    @property
    def quantity_display(self):
        return (str(self.quantity_min) if not self.quantity_max
                else f"{self.quantity_min}–{self.quantity_max}")
    
class WorkoutSession(models.Model):
    """
    One per day & routine variant for each user.
    """
    user            = models.ForeignKey(settings.AUTH_USER_MODEL,
                                        on_delete=models.CASCADE,
                                        related_name="workout_sessions", null=True,   #  allow null for old rows
        blank=True,)
    user_routine = models.ForeignKey("UserRoutine",
                                        on_delete=models.PROTECT,
                                        related_name="sessions", null=True,   #  allow null for old rows
        blank=True,)
    date            = models.DateField(default=timezone.localdate)

    class Meta:
        unique_together = ("user", "user_routine", "date")
        ordering        = ("-date",)

    def __str__(self):
        # Admin/delete confirmation may stringify sessions; guard against dangling FK rows
        # where `user_routine_id` points at a missing UserRoutine (legacy data).
        try:
            routine = self.user_routine
        except Exception:
            routine = f"(missing routine #{getattr(self, 'user_routine_id', None)})"
        return f"{self.user} · {routine} · {self.date}"


class WorkoutEntry(models.Model):
    """
    One finished exercise inside a session.
    """
    session     = models.ForeignKey(WorkoutSession,
                                    on_delete=models.CASCADE,
                                    related_name="entries")
    
    user_routine_exercise = models.ForeignKey(
        "UserRoutineExercise",
        on_delete=models.CASCADE,
        null=True,   #  allow null for old rows
        blank=True,)
    exercise    = models.ForeignKey("Exercise",
                                    on_delete=models.PROTECT)
    points      = models.PositiveIntegerField()
    sets_done   = models.PositiveSmallIntegerField(null=True, blank=True)
    reps_done   = models.PositiveSmallIntegerField(null=True, blank=True)
    duration_s  = models.PositiveSmallIntegerField(null=True, blank=True)  # seconds
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
    def __str__(self):
        return f"{self.session} – {self.exercise}"


class RoutineType(models.TextChoices):
    POSTURE = "posture", "Posture Routine"
    HGH = "hgh", "HGH Routine"


class UserRoutine(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="custom_routines"
    )
    routine_type = models.CharField(
        max_length=20,
        choices=RoutineType.choices,
        default='POSTURE',
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    # Store AI scan score breakdown, e.g. {"spine": 60, "pelvis": 47, ...}
    scan_score = models.JSONField(default=dict)

    # Store optimization breakdown directly in the routine
    optimization_breakdown = models.JSONField(default=dict)

    class Meta:
        verbose_name = "User Routine"
        verbose_name_plural = "User Routines"
        indexes = [
            models.Index(fields=["user", "routine_type", "is_active"])
        ]
        # NOTE:
        # We intentionally do NOT enforce uniqueness on (user, routine_type, is_active)
        # because that would allow only one inactive row too, and MySQL cannot express
        # a partial unique constraint (is_active=true) cleanly across versions.
        #
        # Invariants are enforced in code: at most one active routine per user+type.
        constraints = []

    def __str__(self):
        return f"{self.get_routine_type_display()} for {self.user} ({self.created_at.date()})"


class UserRoutineExercise(models.Model):
    routine = models.ForeignKey(
        UserRoutine,
        on_delete=models.CASCADE,
        related_name="exercises"
    )
    # ✅ ADD THIS LINE
    variant_exercise = models.ForeignKey(
        VariantExercise,
        on_delete=models.PROTECT,
        null=True,      # ✅ IMPORTANT
        blank=True      # ✅ IMPORTANT (admin/forms)
    )
    exercise = models.ForeignKey(
        "Exercise",  # Replace with actual Exercise model path if in another app
        on_delete=models.PROTECT
    )
    tier = models.CharField(
        max_length=6,
        choices=Tier.choices
    )
    order = models.PositiveSmallIntegerField()

    sets = models.PositiveSmallIntegerField(default=2, validators=[MinValueValidator(1)])
    qty_min = models.PositiveSmallIntegerField(default=10, validators=[MinValueValidator(1)])
    qty_max = models.PositiveSmallIntegerField(null=True, blank=True)
    unit = models.CharField(
        max_length=8,
        choices=Unit.choices,
        default=Unit.REPS
    )
    notes = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["routine", "order"]
        unique_together = ("routine", "exercise")

    def __str__(self):
        return f"{self.exercise.name} ({self.tier})"
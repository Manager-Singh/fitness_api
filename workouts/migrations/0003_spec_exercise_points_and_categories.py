from django.db import migrations


def apply_spec_points_and_categories(apps, schema_editor):
    Exercise = apps.get_model("workouts", "Exercise")

    # Spec v3.2 (Sections 5.8 + 4.5) — normalize core exercise points and categories.
    # Keys are matched by `Exercise.name` (case-insensitive, trimmed).
    SPEC_EXERCISES = {
        # Teen/Adult posture exercises (Engine 1)
        "hanging from bar": {"points": 9, "category": "posture"},
        "cobra stretch": {"points": 7, "category": "posture"},
        "hip flexor stretch": {"points": 7, "category": "posture"},
        "wall angels": {"points": 7, "category": "posture"},
        "glute bridges": {"points": 7, "category": "posture"},
        "cat-cow stretch": {"points": 6, "category": "posture"},
        "hamstring stretch": {"points": 6, "category": "posture"},
        "tadasana (mountain pose)": {"points": 6, "category": "posture"},
        "doorway chest stretch": {"points": 6, "category": "posture"},
        "child’s pose with arm walks": {"points": 6, "category": "posture"},
        "child's pose with arm walks": {"points": 6, "category": "posture"},
        "spinal twist stretch": {"points": 6, "category": "posture"},
        "butterfly stretch": {"points": 5, "category": "posture"},
        "chin tucks": {"points": 5, "category": "posture"},
        # Adult-only in spec table
        "pelvic tilts": {"points": 0, "category": "posture"},
        "cat-cow": {"points": 6, "category": "posture"},

        # Teen HGH / Environmental exercises (Engine 2)
        "hgh boost (sprint & burpees)": {"points": 15, "category": "hgh"},
        "jump rope": {"points": 9, "category": "hgh"},
        "box jumps / jump squats": {"points": 9, "category": "hgh"},
        "box jumps": {"points": 9, "category": "hgh"},
        "jump squats": {"points": 9, "category": "hgh"},
        "squats": {"points": 8, "category": "hgh"},
        "bodyweight squats": {"points": 8, "category": "hgh"},
        "high knees": {"points": 8, "category": "hgh"},
        "mountain climbers": {"points": 8, "category": "hgh"},
        "deep squat hold": {"points": 8, "category": "hgh"},
        "lunges": {"points": 7, "category": "hgh"},
        "plank": {"points": 7, "category": "hgh"},
        "superman hold": {"points": 7, "category": "hgh"},
    }

    # Apply updates where names match.
    # (We keep it conservative: only update known names to avoid breaking custom exercises.)
    for ex in Exercise.objects.all():
        name_key = (ex.name or "").strip().lower()
        spec = SPEC_EXERCISES.get(name_key)
        if not spec:
            continue
        changed = False
        pts = int(spec["points"])
        cat = str(spec["category"])
        if ex.points != pts:
            ex.points = pts
            changed = True
        if (ex.category or "").lower() != cat:
            ex.category = cat
            changed = True
        if changed:
            ex.save(update_fields=["points", "category"])


class Migration(migrations.Migration):
    dependencies = [
        ("workouts", "0002_userroutineexercise_variant_exercise_and_more"),
    ]

    operations = [
        migrations.RunPython(apply_spec_points_and_categories, migrations.RunPython.noop),
    ]


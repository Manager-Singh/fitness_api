from django.db import migrations


def backfill_module_nutrition_category(apps, schema_editor):
    Module = apps.get_model("nutration", "Module")

    def _norm(s):
        return (s or "").strip().lower()

    # Backfill using exact module names seen in admin + safe keyword fallback.
    for m in Module.objects.all():
        if m.type != "NUT":
            continue
        if m.nutrition_category:
            continue
        name = _norm(m.name)
        short = _norm(getattr(m, "short_name", ""))

        # Exact known names (from your admin list)
        if name in {"disc lubrication", "spine support & disc lubrication foods"} or short == "disc":
            m.nutrition_category = "disc"
            m.save(update_fields=["nutrition_category"])
            continue
        if name in {"posture muscle repair", "posture muscle repair & fuel foods"} or short == "muscle":
            m.nutrition_category = "muscle"
            m.save(update_fields=["nutrition_category"])
            continue
        if "growthmax" in name:
            m.nutrition_category = "teen"
            m.save(update_fields=["nutrition_category"])
            continue

        # Keyword fallback
        if any(k in name for k in ("disc", "lubric", "spine")):
            m.nutrition_category = "disc"
            m.save(update_fields=["nutrition_category"])
            continue
        if any(k in name for k in ("muscle", "repair", "fuel")):
            m.nutrition_category = "muscle"
            m.save(update_fields=["nutrition_category"])
            continue


class Migration(migrations.Migration):
    dependencies = [
        ("nutration", "0011_module_nutrition_category"),
    ]

    operations = [
        migrations.RunPython(backfill_module_nutrition_category, migrations.RunPython.noop),
    ]


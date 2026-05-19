from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("nutration", "0012_backfill_module_nutrition_category"),
    ]

    operations = [
        migrations.AddField(
            model_name="module",
            name="sort_order",
            field=models.PositiveSmallIntegerField(
                db_index=True,
                default=0,
                help_text="UI ordering within a module type (e.g. Lifestyle 1-4, Nutrition 1-4). Lower comes first.",
            ),
        ),
    ]


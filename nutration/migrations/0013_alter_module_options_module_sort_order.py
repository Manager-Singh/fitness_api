# Combined migration (server-generated name). Equivalent to 0013_module_sort_order + 0014_alter_module_options.
# Use ONE branch only: either this file OR 0013+0014 — not both applied on the same database.

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
        migrations.AlterModelOptions(
            name="module",
            options={"ordering": ("age_group__min_age", "type", "sort_order", "name")},
        ),
    ]

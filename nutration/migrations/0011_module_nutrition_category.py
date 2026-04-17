from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("nutration", "0010_module_action_btn_module_background_image_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="module",
            name="nutrition_category",
            field=models.CharField(
                blank=True,
                choices=[
                    ("disc", "Disc Lubrication (adult)"),
                    ("muscle", "Muscle Repair (adult)"),
                    ("teen", "Teen Nutrition (teen)"),
                    ("other", "Other / Uncategorized"),
                ],
                help_text="Spec routing bucket for nutrition modules (adult disc vs adult muscle).",
                max_length=12,
                null=True,
            ),
        ),
    ]


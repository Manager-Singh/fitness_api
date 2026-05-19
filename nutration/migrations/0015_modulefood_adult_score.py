from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("nutration", "0014_alter_module_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="modulefood",
            name="adult_score",
            field=models.PositiveSmallIntegerField(
                default=1,
                help_text="Adult track: points per log (flat model; usually 1).",
                validators=[MinValueValidator(1)],
            ),
        ),
        migrations.AlterField(
            model_name="modulefood",
            name="score",
            field=models.PositiveSmallIntegerField(
                help_text="Teen track: points per log (variable scores, 35 pt/day cap).",
                validators=[MinValueValidator(1)],
            ),
        ),
    ]

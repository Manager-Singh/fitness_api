from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0014_heightledger_engine1_bio_columns"),
    ]

    operations = [
        migrations.AddField(
            model_name="posturestate",
            name="questionnaire_completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]


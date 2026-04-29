from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0015_posturestate_questionnaire_completed_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="dailylog",
            name="genetic_average_cm",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="dailylog",
            name="daily_genetic_average_gain_cm",
            field=models.FloatField(blank=True, null=True),
        ),
    ]

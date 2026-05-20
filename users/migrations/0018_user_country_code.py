from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0017_dailylog_habit_points"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="country_code",
            field=models.CharField(
                blank=True,
                default="CA",
                help_text="ISO 3166-1 alpha-2 (e.g. CA, US). Used for leaderboard flags.",
                max_length=2,
            ),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0016_dailylog_genetic_average"),
    ]

    operations = [
        migrations.AddField(
            model_name="dailylog",
            name="habit_points",
            field=models.IntegerField(
                default=0,
                help_text="Issue #13 micro-habits (Engine 1), capped at 6/day.",
            ),
        ),
    ]

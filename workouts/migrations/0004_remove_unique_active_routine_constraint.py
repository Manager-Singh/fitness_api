from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("workouts", "0003_spec_exercise_points_and_categories"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="userroutine",
            name="unique_active_routine_per_type",
        ),
    ]


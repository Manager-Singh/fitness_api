from django.db import migrations


def seed_habits(apps, schema_editor):
    MicroHabit = apps.get_model("habits", "MicroHabit")
    rows = [
        {
            "code": "puppet_string_walk",
            "name": "Puppet String Walk",
            "ui_prompt": "Imagined string pulling head up while walking",
            "daily_max_points": 2,
            "logging_mode": "am_pm",
            "points_per_log": 1,
            "sort_order": 1,
        },
        {
            "code": "desk_un_slouch",
            "name": "60-Sec Desk Un-Slouch",
            "ui_prompt": "Sat back, core engaged, shoulders down, 60s",
            "daily_max_points": 2,
            "logging_mode": "am_pm",
            "points_per_log": 1,
            "sort_order": 2,
        },
        {
            "code": "tech_neck_lift",
            "name": "Tech-Neck Lift",
            "ui_prompt": "Held phone at eye level for 15+ min scroll",
            "daily_max_points": 1,
            "logging_mode": "once_daily",
            "points_per_log": 1,
            "sort_order": 3,
        },
        {
            "code": "doorway_posture_reset",
            "name": "Doorway Posture Reset",
            "ui_prompt": "Completed 3 doorway posture resets today",
            "daily_max_points": 1,
            "logging_mode": "once_daily",
            "points_per_log": 1,
            "sort_order": 4,
        },
    ]
    for row in rows:
        MicroHabit.objects.update_or_create(code=row["code"], defaults=row)


def unseed_habits(apps, schema_editor):
    MicroHabit = apps.get_model("habits", "MicroHabit")
    MicroHabit.objects.filter(
        code__in=[
            "puppet_string_walk",
            "desk_un_slouch",
            "tech_neck_lift",
            "doorway_posture_reset",
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("habits", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_habits, unseed_habits),
    ]

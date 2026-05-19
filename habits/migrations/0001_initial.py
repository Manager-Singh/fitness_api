import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MicroHabit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.SlugField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=160)),
                ("ui_prompt", models.TextField(blank=True)),
                ("daily_max_points", models.PositiveSmallIntegerField(default=1)),
                (
                    "logging_mode",
                    models.CharField(
                        choices=[("am_pm", "AM and PM (1 pt each)"), ("once_daily", "Once per day")],
                        default="once_daily",
                        max_length=16,
                    ),
                ),
                ("points_per_log", models.PositiveSmallIntegerField(default=1)),
                ("sort_order", models.PositiveSmallIntegerField(db_index=True, default=0)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ("sort_order", "name"),
            },
        ),
        migrations.CreateModel(
            name="MicroHabitLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("log_date", models.DateField(db_index=True)),
                (
                    "slot",
                    models.CharField(
                        choices=[("am", "AM"), ("pm", "PM"), ("once", "Once")],
                        max_length=8,
                    ),
                ),
                ("points", models.PositiveSmallIntegerField(default=1)),
                ("logged_at", models.DateTimeField(auto_now=True)),
                (
                    "habit",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="logs",
                        to="habits.microhabit",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="micro_habit_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-logged_at",),
            },
        ),
        migrations.AddConstraint(
            model_name="microhabitlog",
            constraint=models.UniqueConstraint(
                fields=("user", "log_date", "habit", "slot"),
                name="unique_micro_habit_log_per_slot",
            ),
        ),
    ]

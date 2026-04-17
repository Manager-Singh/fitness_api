from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0009_friendinvite"),
    ]

    operations = [
        migrations.CreateModel(
            name="PostureState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("scan_completed", models.BooleanField(default=False)),
                ("questionnaire_completed", models.BooleanField(default=False)),
                ("total_recoverable_loss_um", models.BigIntegerField(default=0)),
                ("spinal_current_loss_um", models.BigIntegerField(default=0)),
                ("collapse_current_loss_um", models.BigIntegerField(default=0)),
                ("pelvic_current_loss_um", models.BigIntegerField(default=0)),
                ("legs_current_loss_um", models.BigIntegerField(default=0)),
                ("last_scan_at", models.DateTimeField(blank=True, null=True)),
                ("algorithm_version", models.CharField(default="v1", max_length=30)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="posture_state", to=settings.AUTH_USER_MODEL),
                ),
            ],
        ),
        migrations.CreateModel(
            name="HeightLedger",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("log_date", models.DateField()),
                ("entry_type", models.CharField(max_length=24)),
                ("delta_um", models.BigIntegerField(default=0)),
                ("cumulative_um", models.BigIntegerField(default=0)),
                ("algorithm_version", models.CharField(default="v1", max_length=30)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="height_ledger", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "ordering": ["-log_date", "-created_at"],
            },
        ),
        migrations.CreateModel(
            name="DailyLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("log_date", models.DateField()),
                ("exercise_points", models.IntegerField(default=0)),
                ("food_points", models.IntegerField(default=0)),
                ("lifestyle_points", models.IntegerField(default=0)),
                ("engine1_points", models.IntegerField(default=0)),
                ("engine2_points", models.IntegerField(default=0)),
                ("diary_only_points", models.IntegerField(default=0)),
                ("validated", models.BooleanField(default=False)),
                ("streak_incremented", models.BooleanField(default=False)),
                ("source_tz", models.CharField(blank=True, default="", max_length=80)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="daily_logs", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "ordering": ["-log_date"],
                "unique_together": {("user", "log_date")},
            },
        ),
    ]

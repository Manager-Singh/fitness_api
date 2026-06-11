from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UltimateHeightPrediction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sex", models.CharField(blank=True, default="", max_length=10)),
                ("age_years", models.FloatField(blank=True, null=True)),
                ("current_height_cm", models.FloatField(blank=True, null=True)),
                ("father_height_cm", models.FloatField(blank=True, null=True)),
                ("mother_height_cm", models.FloatField(blank=True, null=True)),
                ("voice_depth", models.PositiveSmallIntegerField(default=0)),
                ("facial_hair", models.PositiveSmallIntegerField(default=0)),
                ("body_hair", models.PositiveSmallIntegerField(default=0)),
                ("adams_apple", models.PositiveSmallIntegerField(default=0)),
                ("menarche_status", models.PositiveSmallIntegerField(default=0)),
                ("growth_spurt_status", models.PositiveSmallIntegerField(default=0)),
                ("recent_growth_cm", models.FloatField(blank=True, null=True)),
                ("wingspan_cm", models.FloatField(blank=True, null=True)),
                ("wrist_circumference_cm", models.FloatField(blank=True, null=True)),
                ("weight_kg", models.FloatField(blank=True, null=True)),
                ("shoe_size", models.FloatField(blank=True, null=True)),
                ("posture_recovery_cm", models.FloatField(default=0.0)),
                ("genetic_potential_cm", models.FloatField(blank=True, null=True)),
                ("true_optimized_cm", models.FloatField(blank=True, null=True)),
                (
                    "band",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("A", "Band A (13.0-17.49, full)"),
                            ("B", "Band B (17.5-20, lite)"),
                            ("20+", "20+ (posture only)"),
                        ],
                        default="",
                        max_length=4,
                    ),
                ),
                ("model_version", models.CharField(blank=True, default="v2", max_length=10)),
                ("completed", models.BooleanField(default=False)),
                ("raw_inputs", models.JSONField(blank=True, default=dict)),
                ("breakdown", models.JSONField(blank=True, default=dict)),
                ("computed_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ultimate_height_predictions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-computed_at"],
            },
        ),
        migrations.AddIndex(
            model_name="ultimateheightprediction",
            index=models.Index(
                fields=["user", "completed", "-computed_at"],
                name="hp_ultpred_user_done_idx",
            ),
        ),
    ]

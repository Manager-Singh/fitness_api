from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0010_posturestate_dailylog_heightledger"),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationEventLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_key", models.CharField(max_length=64)),
                ("event_date", models.DateField()),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notification_event_logs", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "ordering": ["-event_date", "-created_at"],
                "unique_together": {("user", "event_key", "event_date")},
            },
        ),
    ]

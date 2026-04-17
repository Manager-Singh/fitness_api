from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0011_notificationeventlog"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="timezone",
            field=models.CharField(default="UTC", max_length=80),
        ),
        migrations.AddField(
            model_name="user",
            name="last_reset_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="display_name",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="avatar_url",
            field=models.URLField(blank=True, null=True),
        ),
    ]

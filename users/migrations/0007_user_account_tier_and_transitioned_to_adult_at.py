from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0006_user_trial_end_user_trial_start"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="account_tier",
            field=models.CharField(
                blank=True,
                choices=[("teen", "Teen"), ("adult", "Adult")],
                max_length=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="transitioned_to_adult_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

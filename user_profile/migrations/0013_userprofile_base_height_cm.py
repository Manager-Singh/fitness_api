from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("user_profile", "0012_userprofile_birth_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="base_height_cm",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]

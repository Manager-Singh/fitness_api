from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("user_profile", "0011_alter_userprofile_g_p_facial_armpit_hair_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="birth_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]

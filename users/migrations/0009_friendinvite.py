from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0008_friendship"),
    ]

    operations = [
        migrations.CreateModel(
            name="FriendInvite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("invite_token", models.CharField(max_length=64, unique=True)),
                ("expires_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("accepted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="accepted_friend_invites", to="users.user")),
                ("inviter", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sent_friend_invites", to="users.user")),
            ],
        ),
    ]

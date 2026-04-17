from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0007_user_account_tier_and_transitioned_to_adult_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="Friendship",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "Pending"), ("accepted", "Accepted")], default="pending", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user_id_a", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="friendships_sent", to="users.user")),
                ("user_id_b", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="friendships_received", to="users.user")),
            ],
        ),
        migrations.AddConstraint(
            model_name="friendship",
            constraint=models.UniqueConstraint(fields=("user_id_a", "user_id_b"), name="unique_friendship_pair"),
        ),
    ]

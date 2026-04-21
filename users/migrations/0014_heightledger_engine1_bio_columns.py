from django.db import migrations, models


def backfill_engine_deltas(apps, schema_editor):
    """
    Backfill new atomic engine delta columns from existing JSON metadata.

    This keeps existing history fast-queryable without changing external behavior.
    """
    HeightLedger = apps.get_model("users", "HeightLedger")
    db_alias = schema_editor.connection.alias

    qs = HeightLedger.objects.using(db_alias).all().only("id", "engine1_delta_um", "bio_delta_um", "metadata")
    batch = []
    batch_size = 500

    for row in qs.iterator(chunk_size=batch_size):
        md = row.metadata or {}
        try:
            e1 = int(md.get("engine1_delta_um", 0) or 0)
        except Exception:
            e1 = 0
        try:
            bio = int(md.get("bio_delta_um", 0) or 0)
        except Exception:
            bio = 0

        # Only write when we have anything to backfill (avoid unnecessary updates).
        if (row.engine1_delta_um or 0) != e1 or (row.bio_delta_um or 0) != bio:
            row.engine1_delta_um = e1
            row.bio_delta_um = bio
            batch.append(row)

        if len(batch) >= batch_size:
            HeightLedger.objects.using(db_alias).bulk_update(batch, ["engine1_delta_um", "bio_delta_um"])
            batch = []

    if batch:
        HeightLedger.objects.using(db_alias).bulk_update(batch, ["engine1_delta_um", "bio_delta_um"])


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0013_add_engine2_delta_dm"),
    ]

    operations = [
        migrations.AddField(
            model_name="heightledger",
            name="engine1_delta_um",
            field=models.BigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="heightledger",
            name="bio_delta_um",
            field=models.BigIntegerField(default=0),
        ),
        migrations.RunPython(backfill_engine_deltas, migrations.RunPython.noop),
    ]


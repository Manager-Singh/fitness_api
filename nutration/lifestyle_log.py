"""Upsert lifestyle NutraEntry: one row per module per day per session."""

from __future__ import annotations

from nutration.models_log import NutraEntry


def upsert_lifestyle_nutra_entry(
    session,
    *,
    module,
    activity,
    score=None,
    servings=None,
):
    """
    Create or update today's lifestyle log for this module.

    Returns (entry, created) where created is True on insert, False on update.
    Collapses duplicate rows for the same module/day if any exist.
    """
    qs = (
        NutraEntry.objects.filter(
            session=session,
            module=module,
            food__isnull=True,
            activity__isnull=False,
        )
        .order_by("-completed_at", "-id")
    )
    existing = qs.first()
    if existing and qs.count() > 1:
        qs.exclude(pk=existing.pk).delete()

    if existing:
        if activity is not None:
            existing.activity = activity
        if score is not None:
            existing.score = score
        if servings is not None:
            existing.servings = servings or ""
        existing.save()
        return existing, False

    entry = NutraEntry(
        session=session,
        module=module,
        activity=activity,
        score=score,
        servings=servings if servings is not None else "",
    )
    entry.save()
    return entry, True

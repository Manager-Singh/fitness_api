"""Profile display name + timezone helpers for API responses."""
from __future__ import annotations

from utils.country import default_timezone_for_country, should_apply_country_default_timezone


def resolved_display_name(user) -> str | None:
    """Prefer display_name, then name, then username."""
    for attr in ("display_name", "name", "username"):
        val = getattr(user, attr, None)
        if val is not None and str(val).strip():
            return str(val).strip()
    return None


def apply_display_name_to_user(user, raw_name) -> None:
    """Sync name + display_name from a single client-provided label."""
    if raw_name is None:
        return
    label = str(raw_name).strip() or None
    user.display_name = label
    user.name = label


def apply_country_timezone_default(user, country_code: str | None, *, force: bool = False) -> None:
    """
    Set the user's timezone from their country.

    Default (force=False): only fill it in when the user has not chosen a non-UTC zone
    (signup / users still on UTC) so an explicit device/user timezone is never clobbered.

    force=True (use when the country itself is being CHANGED and the same request did not
    also supply an explicit timezone): re-derive from the new country so e.g. a user who
    registered in Canada and switches to Belgium moves to Europe/Brussels. Guardrail: a
    country that maps to bare UTC (unmapped / multi-zone like US) will NOT overwrite an
    already-set zone — we don't downgrade Winnipeg to UTC just because the map has no US row.
    """
    cc = str(country_code or "").strip().upper() if country_code else ""
    if not cc:
        return
    tz = default_timezone_for_country(cc)
    if force:
        if tz != "UTC" or should_apply_country_default_timezone(user):
            user.timezone = tz
        return
    if should_apply_country_default_timezone(user):
        user.timezone = tz

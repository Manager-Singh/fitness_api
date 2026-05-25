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


def apply_country_timezone_default(user, country_code: str | None) -> None:
    """Set timezone from country when user has not chosen a non-UTC zone."""
    cc = str(country_code or "").strip().upper() if country_code else ""
    if not cc or not should_apply_country_default_timezone(user):
        return
    user.timezone = default_timezone_for_country(cc)

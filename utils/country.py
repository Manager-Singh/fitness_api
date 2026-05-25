"""ISO 3166-1 alpha-2 country codes for profile and leaderboard flags."""

DEFAULT_COUNTRY_CODE = "CA"
DEFAULT_TIMEZONE = "UTC"
# Product default for Canada (Central); Canada spans multiple zones — client requested Central.
DEFAULT_TIMEZONE_BY_COUNTRY = {
    "CA": "America/Winnipeg",
}


def default_timezone_for_country(country_code: str | None) -> str:
    cc = normalize_country_code(country_code)
    if cc and cc in DEFAULT_TIMEZONE_BY_COUNTRY:
        return DEFAULT_TIMEZONE_BY_COUNTRY[cc]
    return DEFAULT_TIMEZONE


def should_apply_country_default_timezone(user) -> bool:
    """True when user has no explicit timezone or still on server default UTC."""
    tz = str(getattr(user, "timezone", "") or "").strip()
    return not tz or tz.upper() == "UTC"


def normalize_country_code(value) -> str | None:
    """
    Return uppercase 2-letter A–Z code, or None when missing/invalid.
    Clients treat None as unknown (globe icon).
    """
    if value is None:
        return None
    code = str(value).strip().upper()
    if len(code) != 2 or not code.isalpha():
        return None
    return code


def resolve_country_code(value, *, default: str | None = None) -> str | None:
    """Normalize ``value``; use ``default`` when normalization yields None."""
    normalized = normalize_country_code(value)
    if normalized:
        return normalized
    if default:
        return normalize_country_code(default) or default.upper()[:2]
    return None


def country_flag_emoji(code: str | None) -> str | None:
    """Regional-indicator flag emoji for a valid code; None when unknown."""
    normalized = normalize_country_code(code)
    if not normalized:
        return None
    return "".join(chr(0x1F1E6 - 65 + ord(c)) for c in normalized)

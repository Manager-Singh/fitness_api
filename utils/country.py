"""ISO 3166-1 alpha-2 country codes for profile and leaderboard flags."""

DEFAULT_COUNTRY_CODE = "CA"
DEFAULT_TIMEZONE = "UTC"
# Bug 7a: country -> representative IANA timezone. DST is applied automatically by
# zoneinfo (see utils/user_time.get_user_tz) for these named zones, e.g. Belgium
# resolves to CET (UTC+1) in winter and CEST (UTC+2) in summer.
# Multi-timezone countries (US, AU, RU, ...) are intentionally omitted so they keep the
# UTC fallback rather than guessing a wrong zone; Canada keeps the client-requested
# Central representative.
DEFAULT_TIMEZONE_BY_COUNTRY = {
    "CA": "America/Winnipeg",
    # --- Western / Central Europe (CET / CEST: UTC+1 / +2) ---
    "BE": "Europe/Brussels",
    "NL": "Europe/Amsterdam",
    "LU": "Europe/Luxembourg",
    "FR": "Europe/Paris",
    "DE": "Europe/Berlin",
    "ES": "Europe/Madrid",
    "IT": "Europe/Rome",
    "AT": "Europe/Vienna",
    "CH": "Europe/Zurich",
    "SE": "Europe/Stockholm",
    "NO": "Europe/Oslo",
    "DK": "Europe/Copenhagen",
    "PL": "Europe/Warsaw",
    "CZ": "Europe/Prague",
    "SK": "Europe/Bratislava",
    "HU": "Europe/Budapest",
    "HR": "Europe/Zagreb",
    "SI": "Europe/Ljubljana",
    "RS": "Europe/Belgrade",
    # --- Eastern Europe (EET / EEST: UTC+2 / +3) ---
    "FI": "Europe/Helsinki",
    "GR": "Europe/Athens",
    "RO": "Europe/Bucharest",
    "BG": "Europe/Sofia",
    "EE": "Europe/Tallinn",
    "LV": "Europe/Riga",
    "LT": "Europe/Vilnius",
    "UA": "Europe/Kyiv",
    # --- Western Europe (GMT / BST: UTC+0 / +1) ---
    "GB": "Europe/London",
    "IE": "Europe/Dublin",
    "PT": "Europe/Lisbon",
    "IS": "Atlantic/Reykjavik",
    # --- Middle East / Africa ---
    "TR": "Europe/Istanbul",
    "IL": "Asia/Jerusalem",
    "AE": "Asia/Dubai",
    "SA": "Asia/Riyadh",
    "EG": "Africa/Cairo",
    "ZA": "Africa/Johannesburg",
    "NG": "Africa/Lagos",
    "KE": "Africa/Nairobi",
    "MA": "Africa/Casablanca",
    # --- Asia / Pacific (single-zone) ---
    "IN": "Asia/Kolkata",
    "PK": "Asia/Karachi",
    "BD": "Asia/Dhaka",
    "CN": "Asia/Shanghai",
    "HK": "Asia/Hong_Kong",
    "SG": "Asia/Singapore",
    "MY": "Asia/Kuala_Lumpur",
    "TH": "Asia/Bangkok",
    "PH": "Asia/Manila",
    "JP": "Asia/Tokyo",
    "KR": "Asia/Seoul",
    "NZ": "Pacific/Auckland",
    # --- Latin America (representative) ---
    "MX": "America/Mexico_City",
    "BR": "America/Sao_Paulo",
    "AR": "America/Argentina/Buenos_Aires",
    "CL": "America/Santiago",
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

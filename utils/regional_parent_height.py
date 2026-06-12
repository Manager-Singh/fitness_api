"""
Regional-average parent heights when onboarding stores "I don't know".

Used by Ultimate Height Predictor and genetic MPH fallbacks. Values are approximate
adult stature averages (cm) by country; global default when country unknown.
"""
from __future__ import annotations

from utils.country import normalize_country_code, resolve_country_code, DEFAULT_COUNTRY_CODE

# Approximate adult average heights (cm) — father / mother by country code.
# Source: WHO / national health survey ballparks for genetic-anchor estimates.
COUNTRY_PARENT_HEIGHT_CM: dict[str, tuple[float, float]] = {
    "US": (175.0, 162.0),
    "CA": (175.0, 162.0),
    "GB": (175.0, 161.0),
    "AU": (175.0, 162.0),
    "IN": (165.0, 152.0),
    "PK": (167.0, 154.0),
    "BD": (165.0, 152.0),
    "CN": (172.0, 160.0),
    "JP": (171.0, 158.0),
    "KR": (173.0, 160.0),
    "DE": (178.0, 165.0),
    "FR": (177.0, 164.0),
    "IT": (177.0, 163.0),
    "ES": (174.0, 161.0),
    "BR": (170.0, 158.0),
    "MX": (170.0, 157.0),
    "NG": (167.0, 158.0),
    "ZA": (169.0, 159.0),
    "AE": (173.0, 160.0),
    "SA": (173.0, 158.0),
}

GLOBAL_DEFAULT_FATHER_CM = 175.0
GLOBAL_DEFAULT_MOTHER_CM = 162.0

_ESTIMATE_TYPES = frozenset({"regional", "estimate", "unknown", "dont_know", "i_dont_know"})


def _is_estimate_type(height_type: str | None) -> bool:
    if not height_type:
        return False
    return str(height_type).strip().lower().replace(" ", "_").replace("'", "") in _ESTIMATE_TYPES


def regional_parent_heights_for_country(country_code: str | None) -> tuple[float, float]:
    """Return (father_cm, mother_cm) regional averages for a country."""
    cc = resolve_country_code(country_code, default=DEFAULT_COUNTRY_CODE) or DEFAULT_COUNTRY_CODE
    pair = COUNTRY_PARENT_HEIGHT_CM.get(cc)
    if pair:
        return float(pair[0]), float(pair[1])
    return GLOBAL_DEFAULT_FATHER_CM, GLOBAL_DEFAULT_MOTHER_CM


def resolve_parent_height_cm(profile, user, role: str) -> tuple[float | None, bool]:
    """
    Resolve one parent's height in cm.

    Returns ``(cm, is_estimate)``. When profile has a numeric height, ``is_estimate`` is
    False unless height_type marks it as regional/estimate.
    """
    from height_predictor.services import _safe_float

    role = str(role or "").strip().lower()
    if role not in ("father", "mother"):
        return None, False

    prefix = "father" if role == "father" else "mother"
    raw = getattr(profile, f"{prefix}_height_cm", None)
    height_type = getattr(profile, f"{prefix}_height_type", None)

    cm = _safe_float(raw)
    if cm and cm > 0:
        return float(cm), _is_estimate_type(height_type)

    cc = normalize_country_code(getattr(user, "country_code", None))
    father_cm, mother_cm = regional_parent_heights_for_country(cc)
    return (father_cm if role == "father" else mother_cm), True

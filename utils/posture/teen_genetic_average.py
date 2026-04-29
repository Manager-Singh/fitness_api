"""
Section 5.1 / 5.1b — Genetic_Average (teen) trajectory from MPH + growth_table.

Anchors at age 13 (male: MPH×0.88, female: MPH×0.96), compounds full-year
bracket rates from the Section 5.1 table, then applies the same linear
interp_rate used for Daily_Bio_Gain for the fractional year.

Daily_Genetic_Average_Gain = Genetic_Average × (interp_rate / 100) / 365

Female biological growth completes by 17 (Section 5.1); male curve extends to 21.
"""

from __future__ import annotations

from datetime import date

from utils.age import get_user_age_exact_on_date
from utils.posture.height_constants import compute_mph_simple_cm, normalize_sex

# Section 5.1 age-bracket annual % (13→14 … 20→21)
_MALE_RATES = {13: 3.60, 14: 2.60, 15: 1.90, 16: 1.55, 17: 1.10, 18: 0.75, 19: 0.30, 20: 0.20}
_FEMALE_RATES = {13: 2.25, 14: 1.25, 15: 0.40, 16: 0.10, 17: 0.0, 18: 0.0, 19: 0.0, 20: 0.0}


def _rates(sex: str) -> dict:
    return _FEMALE_RATES if sex == "female" else _MALE_RATES


def teen_growth_interp_rate_percent(sex: str, age_exact: float) -> float:
    """Same interp_rate as Section 5.1 Daily_Bio_Gain (linear between birthday brackets)."""
    if age_exact is None or age_exact < 13.0:
        return 0.0
    sex = str(sex or "").strip().lower()
    if sex not in ("male", "female"):
        sex = "male"
    if sex == "female" and age_exact >= 17.0:
        return 0.0
    rates = _rates(sex)
    age_floor = int(age_exact)
    age_frac = max(0.0, min(1.0, age_exact - age_floor))
    rate_now = float(rates.get(age_floor, 0.0))
    rate_next = float(rates.get(age_floor + 1, 0.0))
    return rate_now + age_frac * (rate_next - rate_now)


def _mph_for_user(user) -> tuple[float, str]:
    from user_profile.models import UserProfile

    profile = UserProfile.objects.filter(user=user).first()
    if not profile:
        return 0.0, "male"
    sex = normalize_sex(getattr(profile, "gender", None)) or "male"
    father = float(getattr(profile, "father_height_cm", None) or 0.0)
    mother = float(getattr(profile, "mother_height_cm", None) or 0.0)
    mph = compute_mph_simple_cm(sex, father, mother)
    return mph, sex


def _genetic_anchor_at_13_cm(mph: float, sex: str) -> float:
    sex = str(sex or "").strip().lower()
    if sex not in ("male", "female"):
        sex = "male"
    return mph * (0.88 if sex == "male" else 0.96)


def _clamp_effective_age(sex: str, age_exact: float) -> float:
    """Female GA curve plateaus from 17; male extends to 21 (chart axis)."""
    if age_exact < 13.0:
        return 13.0
    if sex == "female":
        return min(age_exact, 17.0)
    return min(age_exact, 21.0)


def compute_genetic_average_cm(user, on_date: date | None = None) -> float:
    """
    Genetic_Average in cm at ``on_date`` (decimal age, partial-year factor).
    """
    on_date = on_date or date.today()
    mph, sex = _mph_for_user(user)
    if mph <= 0.0:
        return 0.0

    anchor = _genetic_anchor_at_13_cm(mph, sex)
    age_raw = get_user_age_exact_on_date(user, on_date)
    if age_raw is None:
        return round(anchor, 4)
    if age_raw <= 13.0:
        return round(anchor, 4)

    eff = _clamp_effective_age(sex, age_raw)
    rates = _rates(sex)
    h = float(anchor)
    end_int = int(eff)
    # Full birthday years completed above age 13: multiply bracket starting at y.
    cap_loop = 17 if sex == "female" else 21
    for y in range(13, min(end_int, cap_loop)):
        r = float(rates.get(y, 0.0))
        h *= 1.0 + r / 100.0

    age_frac = eff - float(end_int)
    if age_frac > 1e-9:
        ir = teen_growth_interp_rate_percent(sex, eff)
        h *= 1.0 + (ir / 100.0) * age_frac

    return round(max(0.0, h), 4)


def compute_daily_genetic_average_gain_cm(user, on_date: date | None = None) -> float:
    """Section 5.1b: Genetic_Average × (interp_rate / 100) / 365 for ``on_date``."""
    on_date = on_date or date.today()
    _, sex = _mph_for_user(user)
    age_raw = get_user_age_exact_on_date(user, on_date)
    if age_raw is None or age_raw < 13.0:
        return 0.0
    if sex == "female" and age_raw >= 17.0:
        return 0.0
    if sex != "female" and age_raw > 21.0:
        return 0.0

    ga = compute_genetic_average_cm(user, on_date)
    ir = teen_growth_interp_rate_percent(sex, age_raw)
    if ir <= 0.0:
        return 0.0
    return round(max(0.0, float(ga) * (ir / 100.0) / 365.0), 6)

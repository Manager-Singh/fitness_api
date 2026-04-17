# nutration/utils/age.py
from datetime import date
from django.core.exceptions import ImproperlyConfigured


def get_user_age(user, default='currently') -> int | None:
    """
    Return the user's age in whole years.
    
    If default='register', return None if age is not available.
    If default='currently' (default), return a safe fallback age (25) if age is not found.
    """
    FALLBACK_AGE_YEARS = 25
    try:
        profile = user.profile  # OneToOneField related_name='profile'
    except AttributeError:
        if default == 'register':
            return None
        return FALLBACK_AGE_YEARS

    # Try age field
    years = getattr(profile, "age", None)
    if years:
        try:
            return int(float(years))
        except ValueError:
            if default == 'register':
                return None
            return FALLBACK_AGE_YEARS

    # Try birth_date / date_of_birth if exists
    dob = getattr(profile, "birth_date", None) or getattr(profile, "date_of_birth", None)
    if dob:
        today = date.today()
        return (today - dob).days // 365

    if default == 'register':
        return None
    return FALLBACK_AGE_YEARS


def get_user_age_on_date(user, on_date: date, default="currently") -> int | None:
    """
    Whole years as of ``on_date`` (for historical daily logs / ledger replay).
    Falls back to static ``profile.age`` when no DOB is stored.
    """
    try:
        profile = user.profile
    except AttributeError:
        if default == "register":
            return None
        return 25

    dob = getattr(profile, "birth_date", None) or getattr(profile, "date_of_birth", None)
    if dob:
        return (on_date - dob).days // 365

    years = getattr(profile, "age", None)
    if years:
        try:
            return int(float(years))
        except ValueError:
            if default == "register":
                return None
            return 25

    if default == "register":
        return None
    return 25


def get_user_age_exact_on_date(user, on_date: date) -> float | None:
    """Decimal age on ``on_date``; falls back to numeric age field when no DOB."""
    try:
        profile = user.profile
    except AttributeError:
        return None

    dob = getattr(profile, "birth_date", None) or getattr(profile, "date_of_birth", None)
    if dob:
        return (on_date - dob).days / 365.2425

    raw_age = getattr(profile, "age", None)
    if raw_age in (None, ""):
        return None
    try:
        return float(raw_age)
    except (TypeError, ValueError):
        return None


def get_user_age_exact(user) -> float | None:
    """
    Return decimal age using birth_date when available.
    Falls back to numeric age field.
    """
    try:
        profile = user.profile
    except AttributeError:
        return None

    dob = getattr(profile, "birth_date", None) or getattr(profile, "date_of_birth", None)
    if dob:
        return (date.today() - dob).days / 365.2425

    raw_age = getattr(profile, "age", None)
    if raw_age in (None, ""):
        return None
    try:
        return float(raw_age)
    except (TypeError, ValueError):
        return None
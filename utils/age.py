# nutration/utils/age.py
from datetime import date


def age_years_days_since_last_birthday(dob: date, ref: date | None = None) -> tuple[int, int] | None:
    """
    Completed calendar years since DOB and days since the most recent birthday (as of ref).

    Used for profile copy like "13 years 302 days old". Returns None if dob is missing or ref < dob.
    """
    if dob is None:
        return None
    ref = ref or date.today()
    if ref < dob:
        return None

    def _birthday_in_year(year: int) -> date:
        try:
            return date(year, dob.month, dob.day)
        except ValueError:
            # DOB Feb 29 on a non-leap year
            return date(year, 2, 28)

    bday_this = _birthday_in_year(ref.year)
    if ref < bday_this:
        years = ref.year - dob.year - 1
        last_bday = _birthday_in_year(ref.year - 1)
    else:
        years = ref.year - dob.year
        last_bday = bday_this
    days = (ref - last_bday).days
    return years, max(0, days)


def format_age_exact_years_days(dob: date, ref: date | None = None) -> str | None:
    """Human-readable exact age, e.g. "13 years 302 days old"."""
    parts = age_years_days_since_last_birthday(dob, ref)
    if parts is None:
        return None
    y, d = parts
    return f"{y} years {d} days old"


def _whole_years_from_dob(dob: date, *, on_date: date | None = None) -> int:
    """Whole years from DOB; matches get_user_age_exact-style averaging."""
    ref = on_date or date.today()
    days = max(0, (ref - dob).days)
    return int(days / 365.2425)


def get_user_age(user, default='currently') -> int | None:
    """
    Return the user's age in whole years.

    Prefer birth_date over the stored ``age`` string when both exist so routine
    brackets and teen/adult logic stay aligned with DOB (avoids stale age text).

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

    dob = getattr(profile, "birth_date", None) or getattr(profile, "date_of_birth", None)
    if dob:
        return _whole_years_from_dob(dob)

    years = getattr(profile, "age", None)
    if years not in (None, ""):
        try:
            return int(float(years))
        except ValueError:
            if default == 'register':
                return None
            return FALLBACK_AGE_YEARS

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
        return _whole_years_from_dob(dob, on_date=on_date)

    years = getattr(profile, "age", None)
    if years not in (None, ""):
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
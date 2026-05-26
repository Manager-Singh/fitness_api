"""Canonical account/dashboard tier from decimal age and sex."""

from __future__ import annotations

from utils.age import get_user_age, get_user_age_exact
from utils.paywall_flags import is_adult_age, is_teen_age, user_profile_sex


def desired_account_tier(*, age_exact=None, age_years=None, gender=None, sex=None, user=None) -> str | None:
    if is_teen_age(age_exact, age_years, gender=gender, sex=sex, user=user):
        return "teen"
    if is_adult_age(age_exact, age_years, gender=gender, sex=sex, user=user):
        return "adult"
    return None


def sync_account_tier(user, *, age_exact=None, age_years=None, gender=None, sex=None, save: bool = True) -> str | None:
    """
    Persist ``user.account_tier`` from DOB/age and profile gender.

    Female: teen 13–17, adult 18+. Male: teen 13–20, adult 21+.
    """
    ae = age_exact if age_exact is not None else get_user_age_exact(user)
    ay = age_years if age_years is not None else get_user_age(user, default="register")
    g = gender or sex or user_profile_sex(user)
    desired = desired_account_tier(age_exact=ae, age_years=ay, gender=g, sex=g, user=user)
    if desired is None:
        return getattr(user, "account_tier", None)
    if getattr(user, "account_tier", None) != desired:
        user.account_tier = desired
        if save:
            user.save(update_fields=["account_tier"])
    return desired


def auth_track_fields(user, *, age_exact=None, age_years=None) -> dict:
    """Fields for login/register responses so clients do not infer tier from ``age`` alone."""
    ae = age_exact if age_exact is not None else get_user_age_exact(user)
    ay = age_years if age_years is not None else get_user_age(user, default="register")
    sex = user_profile_sex(user)
    tier = sync_account_tier(user, age_exact=ae, age_years=ay, gender=sex, sex=sex, save=True)
    teen = is_teen_age(ae, ay, gender=sex, sex=sex, user=user)
    return {
        "account_tier": tier,
        "age_exact": ae,
        "gender": sex,
        "is_teen_track": teen,
        "dashboard_variant": "teen" if teen else "adult",
    }

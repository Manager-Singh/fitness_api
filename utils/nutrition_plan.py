"""Gender-aware nutrition plan module visibility (female adult 18+, male adult 21+)."""
from __future__ import annotations

from django.db.models import Q

# Adult catalog rows (e.g. Adult Hydration) are often stored under AgeGroup min_age=21
# even though female adults start at 18.
ADULT_MODULE_CATALOG_MIN_AGE = 21


def module_filter_age(user, age: int, age_exact: float | None = None) -> int:
    """
    Age used to match ``nutration.AgeGroup`` rows when loading modules.

    Female adults (18+) and male adults (21+) can access modules bucketed under
    the 21+ age group in admin (e.g. Adult Hydration) before they turn 21.
    """
    from utils.age import get_user_age_exact
    from utils.paywall_flags import account_age_bounds, is_adult_age

    if age_exact is None:
        age_exact = get_user_age_exact(user)

    if not is_adult_age(age_exact, age, user=user):
        return int(age)

    bounds = account_age_bounds(user=user)
    return max(int(age), int(bounds["adult_min"]), ADULT_MODULE_CATALOG_MIN_AGE)


def modules_for_user_age_q(user, age: int, age_exact: float | None = None) -> Q:
    """Django Q matching age groups for a user (sex-specific adult band)."""
    filter_age = module_filter_age(user, age, age_exact=age_exact)
    return Q(age_group__min_age__lte=filter_age) & (
        Q(age_group__max_age__isnull=True) | Q(age_group__max_age__gte=filter_age)
    )


def account_age_bounds_payload(user, age: int, age_exact: float | None = None) -> dict:
    """Expose sex-specific teen/adult cutoffs on plan APIs for clients."""
    from utils.age import get_user_age_exact
    from utils.paywall_flags import account_age_bounds, is_adult_age, is_teen_age

    if age_exact is None:
        age_exact = get_user_age_exact(user)
    from utils.paywall_flags import user_profile_sex

    bounds = account_age_bounds(user=user)
    return {
        "age": int(age),
        "age_exact": float(age_exact) if age_exact is not None else None,
        "sex": user_profile_sex(user),
        "teen_min": bounds["teen_min"],
        "teen_max": bounds["teen_max"],
        "adult_min": bounds["adult_min"],
        "is_teen": bool(is_teen_age(age_exact, age, user=user)),
        "is_adult": bool(is_adult_age(age_exact, age, user=user)),
        "module_filter_age": module_filter_age(user, age, age_exact=age_exact),
    }

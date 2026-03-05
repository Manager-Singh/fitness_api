from django.utils import timezone

from utils.posture.height_constants import (
    TEEN_MIN_AGE,
    TEEN_MAX_AGE,
    ADULT_MIN_AGE,
)
from utils.posture.teen_height_engine import (
    teen_height_free,
    teen_height_paid,
)
from utils.posture.adult_height_engine import (
    adult_free,
    adult_paid,
)
from utils.posture.height_helpers import safe_int


def _days_since_last_scan(profile):
    """
    Returns number of days since last scan.
    None if never scanned.
    """
    if not profile.last_scan:
        return None

    delta = timezone.now() - profile.last_scan
    return delta.days


def get_height_view(user, profile, is_paid, optimized_height_cm=None,total_score=0):

    # print(profile)
    age = profile.age_years

    days_since_scan = _days_since_last_scan(profile)

    # ---------------------
    # TEENS (13–20)
    # ---------------------
    if TEEN_MIN_AGE <= age <= TEEN_MAX_AGE:
        if not is_paid:
            return {
                "tier": "teen_free",
                **teen_height_free(profile),
                "can_rescan": False,
                "growth_max_active": (
                    days_since_scan is not None and days_since_scan <= 30
                ),
                "days_since_scan": days_since_scan,
            }

        return {
            "tier": "teen_paid",
            **teen_height_paid(
                profile,
                optimized_height_cm,
                total_score,
            ),
            "can_rescan": True,
            "ai_assistant": True,
            "days_since_scan": days_since_scan,
        }

    # ---------------------
    # ADULTS (21+)
    # ---------------------
    if age >= ADULT_MIN_AGE:
        if not is_paid:
            return {
                "tier": "adult_free",
                **adult_free(profile.current_height_cm),
                "can_rescan": False,
                "days_since_scan": days_since_scan,
            }

        return {
            "tier": "adult_paid",
            **adult_paid(
                profile.current_height_cm,
                profile.posture_loss_cm,
                total_score,
            ),
            "can_rescan": True,
            "ai_assistant": True,
            "days_since_scan": days_since_scan,
        }

    return {"error": "Unsupported age"}

"""Global trial toggles (admin-controlled via MonetizationSettings)."""


def teen_trial_globally_enabled() -> bool:
    try:
        from payment_packages.models import MonetizationSettings

        return MonetizationSettings.is_teen_trial_enabled()
    except Exception:
        return True

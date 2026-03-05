# nutration/utils/age.py
from datetime import date
from django.core.exceptions import ImproperlyConfigured


def get_user_age(user, default='currently') -> int | None:
    """
    Return the user's age in whole years.
    
    If default='register', return None if age is not available.
    If default='currently' (default), raise error if age is not found.
    """
    try:
        profile = user.profile  # OneToOneField related_name='profile'
    except AttributeError:
        if default == 'register':
            return None
        raise ImproperlyConfigured("User has no related profile object")

    # Try age field
    years = getattr(profile, "age", None)
    if years:
        try:
            return int(float(years))
        except ValueError:
            if default == 'register':
                return None
            raise ImproperlyConfigured("Profile.age must be numeric")

    # Try date_of_birth if exists
    dob = getattr(profile, "date_of_birth", None)
    if dob:
        today = date.today()
        return (today - dob).days // 365

    if default == 'register':
        return None

    raise ImproperlyConfigured("Profile missing 'age' or 'date_of_birth'.")
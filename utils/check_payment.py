# from datetime import timedelta
# from django.utils import timezone
# from rest_framework.response import Response
# from user_profile.models import Payment


# def check_subscription_or_response(user):
#     latest_payment = (
#         Payment.objects.filter(
#             user=user,
#             payment_status__iexact="succeeded"
#         )
#         .order_by('-created_at')
#         .select_related('package')
#         .first()
#     )

#     if not latest_payment:
#         return Response({
#             "expired": True,
#             "days_left": 0,
#             "message": "No active subscription"
#         }, status=403)

#     duration_months = int(latest_payment.package.duration)
#     expiry_date = latest_payment.created_at + timedelta(days=duration_months * 30)

#     now = timezone.now()
#     if expiry_date < now:
#         return Response({
#             "expired": True,
#             "days_left": 0,
#             "message": "Subscription expired"
#         }, status=403)

#     days_left = (expiry_date - now).days
#     return Response({
#         "expired": False,
#         "days_left": days_left,
#         "message": "Subscription active"
#     }, status=200)

from datetime import timedelta
from django.utils import timezone
from rest_framework.response import Response
from rest_framework import status
from user_profile.models import Payment
from utils.age import get_user_age_exact


# def check_subscription_or_response(user):
#     """
#     ✅ Check if user has an active subscription (free or paid).
#     Free vs Paid is determined by package.is_free
#     """
#     now = timezone.now()

#     # Trial check
#     is_trial = False
#     trial_start = user.trial_start
#     trial_end = user.trial_end

#     if trial_start and trial_end:
#         if trial_start <= now <= trial_end:
#             is_trial = True

#     latest_payment = (
#         Payment.objects.filter(
#             user=user,
#             payment_status="succeeded"   # ✅ FIX
#         )
#         .select_related("package")
#         .order_by("-created_at")
#         .first() 
#     )

#     print(latest_payment)

#     # ❌ No subscription
#     if not latest_payment:
#         return Response({
#             "expired": True,
#             "days_left": 0,
#             "plan": None,
#             "plan_type": None,
#             "is_paid": None,
#             "is_trial": is_trial,
#             "trial_start": trial_start,
#             "trial_end": trial_end,
#             "message": "No active subscription found."
#         }, status=status.HTTP_403_FORBIDDEN)

#     package = latest_payment.package

#     # Safe duration
#     try:
#         duration_months = int(package.duration)
#     except (ValueError, TypeError):
#         duration_months = 3

#     expiry_date = latest_payment.created_at + timedelta(days=duration_months * 30)
#     now = timezone.now()

#     # ❌ Expired
#     if expiry_date < now:
#         return Response({
#             "expired": True,
#             "days_left": 0,
#             "plan": package.name,
#             "plan_type": "Free" if package.is_free else "Paid",
#             "is_paid" : not package.is_free,
#             "message": f"Your {package.name} plan has expired."
#         }, status=status.HTTP_403_FORBIDDEN)

#     # ✅ Active
#     days_left = (expiry_date - now).days

#     return Response({
#         "expired": False,
#         "days_left": days_left,
#         "plan": package.name,
#         "plan_type": "Free" if package.is_free else "Paid",
#         "is_paid" : not package.is_free,
#         "duration": package.get_duration_display(),
#         "message": f"{'Free' if package.is_free else 'Paid'} subscription active ({days_left} days left)."
#     }, status=status.HTTP_200_OK)


def check_subscription_or_response(user):

    now = timezone.now()

    trial_start = user.trial_start
    trial_end = user.trial_end
    age_exact = get_user_age_exact(user)
    is_teen = bool(age_exact is not None and 13.0 <= float(age_exact) < 21.0)
    trial_day = None

    # 🔎 Check subscription
    latest_payment = (
        Payment.objects.filter(
            user=user,
            payment_status="succeeded"
        )
        .select_related("package")
        .order_by("-created_at")
        .first()
    )

    # PAID must override trial (product expectation): if user purchased a paid plan,
    # the response must reflect paid access even if trial window is still active.
    if latest_payment:
        package = latest_payment.package
        try:
            duration_months = int(package.duration)
        except (ValueError, TypeError):
            duration_months = 3
        expiry_date = latest_payment.created_at + timedelta(days=duration_months * 30)
        if expiry_date >= now:
            days_left = (expiry_date - now).days
            if not bool(package.is_free):
                return Response(
                    {
                        "expired": False,
                        "days_left": days_left,
                        "plan": package.name,
                        "plan_type": "Paid",
                        "is_paid": True,
                        "is_trial": False,
                        "trial_start": trial_start,
                        "trial_end": trial_end,
                        "trial_day": int((now - trial_start).total_seconds() // 86400) + 1 if (is_teen and trial_start) else None,
                        "age_exact": age_exact,
                        "duration": package.get_duration_display(),
                        "message": f"Paid subscription active ({days_left} days left).",
                    },
                    status=status.HTTP_200_OK,
                )

    # ✅ Trial check (only when not currently paid)
    if is_teen and trial_start and trial_end and trial_start <= now <= trial_end:
        days_left = (trial_end - now).days
        trial_day = int((now - trial_start).total_seconds() // 86400) + 1
        return Response(
            {
                "expired": False,
                "days_left": days_left,
                "plan": "Trial",
                "plan_type": "Free",
                "is_paid": False,
                "is_trial": True,
                "trial_start": trial_start,
                "trial_end": trial_end,
                "trial_day": trial_day,
                "age_exact": age_exact,
                "message": f"Trial active ({days_left} days left).",
            },
            status=status.HTTP_200_OK,
        )

    if not latest_payment:
        trial_day = int((now - trial_start).total_seconds() // 86400) + 1 if (is_teen and trial_start) else None
        # Spec-aligned free continuation after trial: app remains usable.
        return Response({
            "expired": False,
            "days_left": 0,
            "plan": "Free",
            "plan_type": "Free",
            "is_paid": False,
            "is_trial": False,
            "trial_start": trial_start,
            "trial_end": trial_end,
            "trial_day": trial_day,
            "age_exact": age_exact,
            "message": "Free access active."
        }, status=status.HTTP_200_OK)

    package = latest_payment.package

    try:
        duration_months = int(package.duration)
    except (ValueError, TypeError):
        duration_months = 3

    expiry_date = latest_payment.created_at + timedelta(days=duration_months * 30)

    if expiry_date < now:
        trial_day = int((now - trial_start).total_seconds() // 86400) + 1 if (is_teen and trial_start) else None
        return Response({
            "expired": False,
            "days_left": 0,
            "plan": "Free",
            "plan_type": "Free",
            "is_paid": False,
            "is_trial": False,
            "trial_start": trial_start,
            "trial_end": trial_end,
            "trial_day": trial_day,
            "age_exact": age_exact,
            "message": f"{package.name} expired. Free access active."
        }, status=status.HTTP_200_OK)

    days_left = (expiry_date - now).days

    return Response({
        "expired": False,
        "days_left": days_left,
        "plan": package.name,
        "plan_type": "Free" if package.is_free else "Paid",
        "is_paid": not package.is_free,
        "is_trial": False,
        "trial_start": trial_start,
        "trial_end": trial_end,
        "trial_day": int((now - trial_start).total_seconds() // 86400) + 1 if (is_teen and trial_start) else None,
        "age_exact": age_exact,
        "duration": package.get_duration_display(),
        "message": f"{'Free' if package.is_free else 'Paid'} subscription active ({days_left} days left)."
    }, status=status.HTTP_200_OK)
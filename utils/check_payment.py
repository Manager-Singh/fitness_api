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


def check_subscription_or_response(user):
    """
    ✅ Check if user has an active subscription (free or paid).
    Free vs Paid is determined by package.is_free
    """

    latest_payment = (
        Payment.objects.filter(
            user=user,
            payment_status="succeeded"   # ✅ FIX
        )
        .select_related("package")
        .order_by("-created_at")
        .first() 
    )

    print(latest_payment)

    # ❌ No subscription
    if not latest_payment:
        return Response({
            "expired": True,
            "days_left": 0,
            "plan": None,
            "plan_type": None,
            "is_paid": None,
            "message": "No active subscription found."
        }, status=status.HTTP_403_FORBIDDEN)

    package = latest_payment.package

    # Safe duration
    try:
        duration_months = int(package.duration)
    except (ValueError, TypeError):
        duration_months = 3

    expiry_date = latest_payment.created_at + timedelta(days=duration_months * 30)
    now = timezone.now()

    # ❌ Expired
    if expiry_date < now:
        return Response({
            "expired": True,
            "days_left": 0,
            "plan": package.name,
            "plan_type": "Free" if package.is_free else "Paid",
            "is_paid" : not package.is_free,
            "message": f"Your {package.name} plan has expired."
        }, status=status.HTTP_403_FORBIDDEN)

    # ✅ Active
    days_left = (expiry_date - now).days

    return Response({
        "expired": False,
        "days_left": days_left,
        "plan": package.name,
        "plan_type": "Free" if package.is_free else "Paid",
        "is_paid" : not package.is_free,
        "duration": package.get_duration_display(),
        "message": f"{'Free' if package.is_free else 'Paid'} subscription active ({days_left} days left)."
    }, status=status.HTTP_200_OK)

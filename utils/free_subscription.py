from user_profile.models import Payment
from payment_packages.models import PaymentPackage
from utils.check_payment import check_subscription_or_response
from decimal import Decimal
import uuid

def activate_free_subscription(user):
    """Automatically activate a free subscription for the given user."""

    # Check if user already has an active subscription
    subscription_status = check_subscription_or_response(user)
    if not subscription_status.data.get("expired", True):
        return None  # User already has active plan

    # Get free package
    free_package = PaymentPackage.objects.filter(
        is_free=True,
        deleted_at__isnull=True
    ).first()

    if not free_package:
        return None

    # ✅ Create FREE payment as SUCCESS
    payment = Payment.objects.create(
        user=user,
        package=free_package,
        payment_id=f"FREE-{uuid.uuid4().hex[:8]}",
        payment_status='succeeded',     # ✅ FIX
        payment_method='free',          # ✅ FIX (semantic)
        amount=Decimal('0.00'),
        currency='usd',
        complete_response='Auto free plan activation'
    )

    return payment

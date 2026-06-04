from django.db import models

from payment_packages.duration_utils import format_duration_label, package_duration_days


class PaymentPackage(models.Model):
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_free = models.BooleanField(default=False, help_text="Mark this package as free")
    image = models.ImageField(upload_to='payment_packages/', blank=True, null=True)
    duration = models.CharField(
        max_length=2,
        help_text="Stored code (set via admin amount + unit dropdowns).",
    )
    description = models.TextField(blank=True, null=True)

    # ✅ Store multiple features as JSON
    features = models.JSONField(default=list, blank=True, help_text="List of package features")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({'Free' if self.is_free else f'₹{self.amount}'}) - {self.get_duration_display()}"

    def get_duration_display(self) -> str:
        return format_duration_label(self.duration)

    def duration_in_days(self) -> int:
        """Subscription length in days (used for expiry / days_left)."""
        return package_duration_days(self.duration)

    def save(self, *args, **kwargs):
        # Auto-set amount=0 if free
        if self.is_free:
            self.amount = 0
        super().save(*args, **kwargs)

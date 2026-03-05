from django.db import models

DURATION_CHOICES = [
    ('3', '3 Months'),
    ('6', '6 Months'),
    ('9', '9 Months'),
    ('12', '12 Months'),
]


class PaymentPackage(models.Model):
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_free = models.BooleanField(default=False, help_text="Mark this package as free")
    image = models.ImageField(upload_to='payment_packages/', blank=True, null=True)
    duration = models.CharField(max_length=2, choices=DURATION_CHOICES)
    description = models.TextField(blank=True, null=True)

    # ✅ Store multiple features as JSON
    features = models.JSONField(default=list, blank=True, help_text="List of package features")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({'Free' if self.is_free else f'₹{self.amount}'}) - {self.get_duration_display()}"

    def save(self, *args, **kwargs):
        # Auto-set amount=0 if free
        if self.is_free:
            self.amount = 0
        super().save(*args, **kwargs)

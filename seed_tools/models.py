from __future__ import annotations

from django.conf import settings
from django.db import models


class UserDataSeedRun(models.Model):
    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="seed_runs_created"
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="seed_runs_target"
    )

    params = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SUCCESS)
    result = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "User data seed run"
        verbose_name_plural = "User data seed runs"

    def __str__(self) -> str:
        return f"SeedRun#{self.pk} target_user={self.target_user_id} {self.status}"


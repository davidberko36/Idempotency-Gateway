from django.db import models
from django.utils import timezone
from datetime import timedelta


def default_expires_at():
    return timezone.now() + timedelta(hours=24)


class UserAccount(models.Model):
    name = models.CharField(max_length=100)
    balance = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.name} (balance: {self.balance})"


class IdempotencyRecord(models.Model):
    class Status(models.TextChoices):
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'

    idempotency_key = models.CharField(max_length=256, unique=True)
    request_body_hash = models.CharField(max_length=64)
    response_body = models.JSONField(default=dict)
    response_status = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROCESSING)
    expires_at = models.DateTimeField(default=default_expires_at)
    created_at = models.DateTimeField(auto_now_add=True)

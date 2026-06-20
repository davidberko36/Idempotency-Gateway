from django.db import models

# Create your models here.
class IdempotencyRecord(models.Model):
    idempotency_key = models.CharField(max_length=256, unique=True)
    request_body_hash = models.CharField(max_length=64)
    response_body = models.JSONField()
    response_status = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
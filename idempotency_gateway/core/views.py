import hashlib
import json
import time
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import IdempotencyRecord, UserAccount
from .serializers import PaymentSerializer, UserSerializer


@api_view(['POST'])
def create_user(request):
    serializer = UserSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    user = serializer.save()
    return Response(UserSerializer(user).data, status=201)


@api_view(['GET'])
def get_user(request, user_id):
    try:
        user = UserAccount.objects.get(pk=user_id)
    except UserAccount.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)
    return Response(UserSerializer(user).data)


@api_view(['POST'])
def process_payment(request):
    idempotency_key = request.headers.get("Idempotency-Key")
    if not idempotency_key:
        return Response({'error': 'Idempotency-Key header is required'}, status=400)

    serializer = PaymentSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    body_hash = hashlib.sha256(
        json.dumps(request.data, sort_keys=True).encode()
    ).hexdigest()

    created = False
    try:
        with transaction.atomic():
            record, created = IdempotencyRecord.objects.get_or_create(
                idempotency_key=idempotency_key,
                defaults={
                    'request_body_hash': body_hash,
                    'status': IdempotencyRecord.Status.PROCESSING,
                },
            )
    except IntegrityError:
        record = IdempotencyRecord.objects.get(idempotency_key=idempotency_key)

    if not created:
        if timezone.now() > record.expires_at:
            return Response(
                {'error': 'Idempotency key has expired. Please use a new key.'},
                status=410,
            )

        if record.request_body_hash != body_hash:
            return Response(
                {'error': 'Idempotency key already used for a different request body.'},
                status=422,
            )

        if record.status == IdempotencyRecord.Status.PROCESSING:
            for _ in range(30):
                time.sleep(0.5)
                record.refresh_from_db()
                if record.status == IdempotencyRecord.Status.COMPLETED:
                    break
            else:
                return Response(
                    {'error': 'Timed out waiting for in-flight transaction to complete.'},
                    status=503,
                )

        response = Response(record.response_body, status=record.response_status)
        response['X-Cache-Hit'] = 'true'
        return response

    time.sleep(2)

    user_id = request.data.get("user_id")
    amount = Decimal(str(request.data.get("amount")))
    currency = request.data.get("currency")

    try:
        with transaction.atomic():
            user = UserAccount.objects.select_for_update().get(pk=user_id)
            if user.balance < amount:
                record.delete()
                return Response(
                    {'error': f'Insufficient balance. Current balance: {user.balance} {currency}'},
                    status=400,
                )
            previous_balance = user.balance
            user.balance = F('balance') - amount
            user.save()
            user.refresh_from_db()
    except UserAccount.DoesNotExist:
        record.delete()
        return Response({'error': 'User not found'}, status=404)

    response_body = {
        'message': f'Charged {amount} {currency}',
        'user_id': user_id,
        'previous_balance': str(previous_balance),
        'new_balance': str(user.balance),
    }

    record.response_body = response_body
    record.response_status = 201
    record.status = IdempotencyRecord.Status.COMPLETED
    record.save()

    return Response(response_body, status=201)

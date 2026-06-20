from django.shortcuts import render
from .models import IdempotencyRecord
from .serializers import PaymentSerializer
import hashlib
import json
import time
from rest_framework.decorators import api_view
from rest_framework.response import Response


# Create your views here.
@api_view(['POST'])
def process_payment(request):
    idempotency_key = request.headers.get("Idempotency-Key")
    if not idempotency_key:
        return Response({'error': 'Idempotency-Key header is required'})
    
    serializer = PaymentSerializer(data=request.data)
    validated = getattr(serializer, "validated_data", {}) or {}
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    
    body_hash = hashlib.sha256(
        json.dumps(request.data, sort_keys=True).encode()
    ).hexdigest()

    try:
        record = IdempotencyRecord.objects.get(Idempotency_key=idempotency_key)

        if record.request_body_hash != body_hash:
            return Response(
                {'error': 'Idempotency key has been used for a different request'},
                status=422
            )
        
        response = Response(record.response_body, status=record.response_status)
        response['X-Cache-Hit'] = 'true'
        return response
    
    except IdempotencyRecord.DoesNotExist:
        pass

    time.sleep(2)

    amount = validated.get("amount")
    currency = validated.get("currency")
    response_body = {'message': f'Charged {amount} {currency}'}

    IdempotencyRecord.objects.create(
        idempotency_key=idempotency_key,
        request_body=body_hash,
        response_body=response_body,
        response_status=201,
    )

    return Response(response_body, status=201)

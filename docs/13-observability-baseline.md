# Observability Baseline (Phase 0)

## Scope

Bu fazda amac, her HTTP isteginin izlenebilir olmasi ve kritik aksiyonlar icin audit modelinin hazir olmasidir.

## Implemented Baseline

- JSON formatli structured log eventi (`app/logging_utils.py`)
- Request baslangic/bitis loglari (`http_request_started`, `http_request_completed`)
- Her response'ta `X-Request-ID` header'i
- `audit_logs` tablosu icin migration ve model

## Request ID Standard

- Client `X-Request-ID` gonderirse korunur.
- Gondermezse sistem UUID uretir.
- Log event'lerinde ayni `request_id` yazilir.

## Audit Standard

MVP icin hedeflenen audit kayit alanlari:

- actor_type (`system` / `user`)
- actor_id
- action
- entity_type
- entity_id
- metadata_json
- created_at

## Next Step

Parser approval endpointleri eklendiginde her approve/reject aksiyonunun `audit_logs` tablosuna yazilmasi zorunlu olacaktir.

# API Contracts (Draft)

## Base

- Base path: `/api`
- Auth mode (MVP): single-user bearer token
- Response format: JSON

### Auth Header

- Protected endpointler icin:
  - `Authorization: Bearer <API_AUTH_TOKEN>`
- Public endpoint:
  - `GET /api/health`

### Idempotency Header

- `POST /api/mail-ingestion/sync` icin opsiyonel:
  - `Idempotency-Key: <unique-value>`
- Ayni key tekrar gonderilirse mevcut run sonucu doner (`idempotent=true`).

### Gmail OAuth Notes

- Gmail icin onerilen yontem: OAuth2 + XOAUTH2
- Scope: `https://mail.google.com/`
- `POST /api/mail-accounts` isteginde:
  - `provider=gmail`
  - `auth_mode=oauth_gmail`
  - `oauth_refresh_token=<token>`

## Health

- `GET /api/health`
  - `200 OK`
  - `{ "status": "ok", "service": "ekstrehub-api" }`

## Auth

- `GET /api/auth/session`
  - Token dogrulama sonucu
  - `200 OK` -> `{ "status": "ok", "authenticated": true }`

## Cards

- `GET /api/cards`
  - Kart listesi (protected)
- `POST /api/cards`
  - Kart ekleme (bank_name, card_alias, card_last4)
- `PATCH /api/cards/{cardId}`
  - Kart metadata guncelleme

## Statements

- `GET /api/statements?month=YYYY-MM`
  - Aylik statement listesi
- `GET /api/statements/{statementId}`
  - Statement detay + itemlar
- `POST /api/statements/manual`
  - Manuel statement girisi (MVP fallback)

## Mail Ingestion

- `GET /api/mail-accounts`
  - Tanimli mail hesaplarini listeler (protected)
- `POST /api/mail-accounts`
  - Yeni IMAP hesap tanimi ekler (protected)
  - `auth_mode=password|oauth_gmail`
  - Gmail icin `oauth_gmail` tercih edilir
  - Provider defaults:
    - `provider=gmail` -> `imap.gmail.com:993`
    - `provider=outlook` -> `outlook.office365.com:993`
- `POST /api/mail-ingestion/sync`
  - Mail kutusundan anlik ingestion calistirir (protected)
  - Opsiyonel: `mail_account_id=<id>`
- `GET /api/mail-ingestion/runs?limit=20`
  - Son ingestion run listesini doner (protected)
  - Cursor pagination:
    - `cursor=<last_run_id>`
  - Opsiyonel filtreler:
    - `status=running|completed|completed_with_errors|failed`
    - `started_from=<ISO_DATETIME>`
    - `started_to=<ISO_DATETIME>`
- `GET /api/mail-ingestion/runs/{runId}`
  - Ingestion run sonucu (protected)
  - Liste response'unda `next_cursor` alani bulunur.

## Fees and Alerts

- `GET /api/fees?month=YYYY-MM`
  - Aidat/ek ucret kayitlari
- `GET /api/alerts/upcoming-due`
  - Yaklasan odeme alarmlari

## Parser Governance

- `GET /api/parser/changes?status=pending`
  - Onay bekleyen parser degisimleri (protected)
- `POST /api/parser/changes/{changeId}/approve`
  - Candidate parser onayla (protected)
- `POST /api/parser/changes/{changeId}/reject`
  - Candidate parser reddet (protected)

## Reports

- `GET /api/reports/monthly?month=YYYY-MM`
  - Aylik ozet rapor
- `GET /api/reports/trend?months=6`
  - Trend verisi

## Error Shape

Tum hata cevaplari:

```json
{
  "error": {
    "code": "STRING_CODE",
    "message": "Human readable message",
    "details": {}
  }
}
```

## Error Codes (v0 Catalog)

- `AUTH_MISSING_TOKEN`
- `AUTH_INVALID_FORMAT`
- `AUTH_INVALID_TOKEN`
- `INGESTION_SYNC_FAILED`
- `INGESTION_RUN_NOT_FOUND`
- `MAIL_ACCOUNT_NOT_FOUND`
- `GMAIL_OAUTH_REFRESH_FAILED`
- `HTTP_ERROR`

## Idempotency and Dedup

- Mail ingestion tarafinda `message_id` ve `doc_hash` duplicate korumasi zorunludur.

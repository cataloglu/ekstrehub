# Gmail OAuth Integration

## Why

Gmail tarafinda guncel ve onerilen IMAP auth modeli OAuth2 XOAUTH2'dir. Password-only girisler kademeli olarak kisitlandigi icin Gmail hesaplari icin OAuth tabanli entegrasyon tercih edilir.

## Required Inputs

- `GMAIL_OAUTH_CLIENT_ID`
- `GMAIL_OAUTH_CLIENT_SECRET`
- `oauth_refresh_token` (mail account bazli)

## Mail Account Setup

`POST /api/mail-accounts` ornek payload:

```json
{
  "provider": "gmail",
  "auth_mode": "oauth_gmail",
  "account_label": "Primary Gmail",
  "imap_host": "imap.gmail.com",
  "imap_port": 993,
  "imap_user": "user@gmail.com",
  "imap_password": "",
  "oauth_refresh_token": "REFRESH_TOKEN",
  "mailbox": "INBOX",
  "unseen_only": true,
  "fetch_limit": 20,
  "retry_count": 3,
  "retry_backoff_seconds": 1.5,
  "is_active": true
}
```

## Runtime Flow

1. Ingestion selected mail account'i yukler.
2. `oauth_refresh_token` ile access token yeniler.
3. IMAP baglantisinda `AUTHENTICATE XOAUTH2` kullanir.
4. Mesaj/ek ingestion normal pipeline ile devam eder.

## Security Notes

- Refresh token ve client secret loglara yazilmaz.
- Refresh token saklama modeli sonraki fazda secret manager'a tasinacak.
- OAuth hatalari ingestion run ve audit log tarafinda izlenir.

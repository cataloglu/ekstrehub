# Gmail OAuth Setup Checklist

Bu checklist, Gmail IMAP icin OAuth2 XOAUTH2 entegrasyonunu adim adim devreye almak icindir.

## 1) Google Cloud Project

- [ ] Yeni bir Google Cloud projesi olustur.
- [ ] Faturalandirma durumu ve org policy kisitlarini kontrol et.
- [ ] Project icinde gerekli ekip erisimlerini ver.

## 2) APIs and OAuth Consent

- [ ] Gmail API'yi enable et.
- [ ] OAuth consent screen olustur.
- [ ] Uygulama adini ve support email bilgisini gir.
- [ ] Scope olarak `https://mail.google.com/` tanimla.
- [ ] Test user listesini ekle (publish oncesi).

## 3) OAuth Client Credentials

- [ ] OAuth client type sec (Web/Desktop akisina gore).
- [ ] Redirect URI'leri dogru tanimla.
- [ ] `client_id` ve `client_secret` al.
- [ ] Proje secret store'una kaydet (kod icine yazma).

## 4) Refresh Token Acquisition

- [ ] Offline access ile auth code flow calistir.
- [ ] Refresh token al ve guvenli depola.
- [ ] Tokenin revoke edilmedigini dogrula.

## 5) EkstreHub Environment

- [ ] `.env` icine:
  - [ ] `GMAIL_OAUTH_CLIENT_ID`
  - [ ] `GMAIL_OAUTH_CLIENT_SECRET`
- [ ] `POST /api/mail-accounts` ile account kaydi:
  - [ ] `provider=gmail`
  - [ ] `auth_mode=oauth_gmail`
  - [ ] `oauth_refresh_token` dolu

## 6) Runtime Validation

- [ ] `POST /api/mail-ingestion/sync?mail_account_id=<id>` cagir.
- [ ] Run sonucu `completed` veya `completed_with_errors` donuyor mu kontrol et.
- [ ] Hata durumda `GMAIL_OAUTH_REFRESH_FAILED` kodunu izle.

## 7) Operational Hardening

- [ ] Refresh token rotasyon politikasi tanimla.
- [ ] Token revoke durumunda yeniden yetkilendirme akisi hazirla.
- [ ] Audit log ve alarm kurallari olustur.

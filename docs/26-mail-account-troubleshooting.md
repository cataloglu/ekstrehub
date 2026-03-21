# Mail hesabı ekleme — bilinen sorunlar ve denetim listesi

## Ingress / siyah ekran 404 (1.0.21)

- **Semptom:** HA panelde add-on açılınca siyah alanda `404: Not Found` (veya boş sayfa).
- **Neden (HA kaynak kodu):** Core, add-on’a giden isteklere `X-Ingress-Path: /api/hassio_ingress/{token}` ekler (`homeassistant/components/hassio/ingress.py`). Adres çubuğundaki **`/app/<slug>`** ile bu önek **aynı değildir**. `<base href>` yanlışlıkla `/app/...` veya `location.pathname` ile ayarlanırsa `./assets/...` yanlış host path’e gider.
- **Çözüm:** Sunucu `index.html` içinde `<base href>` değerini **öncelikle `X-Ingress-Path`** ile üretir. Ayrıntı: `docs/27-home-assistant-ingress-urls.md`.

## `?oauth=not_configured` ile 404 (1.0.24)

- **Neden:** Yönlendirme yanlışlıkla `.../hassio_ingress/TOKEN?oauth=...` (TOKEN sonunda `/` yok) olabiliyordu; HA bu path’te 404 döner.
- **Çözüm:** `.../TOKEN/?oauth=not_configured` (sürüm 1.0.24+). Asıl kalıcı çözüm: add-on’da Gmail OAuth Client ID/Secret tanımlamak.

## `AUTHENTICATIONFAILED` / Invalid credentials (Gmail)

- **Neden:** Gmail, IMAP için **hesap şifreni** kabul etmez (güvenlik). **Uygulama şifresi** (16 karakter) veya **OAuth** gerekir.
- **Ne yap:** Google → Güvenlik → 2 adımlı doğrulama → [Uygulama şifreleri](https://myaccount.google.com/apppasswords) → yeni şifre oluştur → EkstreHub’da Mail & Sync’te bu şifreyi gir.

## Gmail “bağlan” tıklanınca URL açılmıyor (1.0.23)

- **Neden:** Home Assistant Ingress iframe’i bazen varsayılan `<a href>` ile yeni sekmeyi engeller.
- **Çözüm:** Arayüz `window.open` dener; engellenirse aynı sekmede yönlendirir.

## Gmail OAuth 404 (1.0.17)

- **Semptom:** “Gmail’e bağlan” tıklanınca `404: Not Found` (genelde HA Ingress altında).
- **Neden:** Göreli `api/oauth/gmail/start` linki `<base href>` ile yanlış host/path’e çözülüyordu.
- **Çözüm:** Link `apiUrlPath()` ile `<base href>` ile çözülür (fetch ile aynı taban).

## Kritik UI hatası (1.0.15 ile düzeltildi)

- **Semptom:** Gmail + uygulama şifresi kullanırken “Create failed 422” veya `imap_password` doğrulama hatası.
- **Neden:** Gmail seçiliyken arayüz her zaman “OAuth refresh token” textarea’sını gösteriyordu; API ise şifre modunda `imap_password` (şifre input’u) bekliyordu. Uygulama şifresi textarea’ya yazılınca sunucuya boş şifre gidiyordu.
- **Çözüm:** `resolvedMailAuthMode === "oauth_gmail"` iken textarea, aksi halde şifre alanı gösterilir.

## Diğer kontroller

| Konu | Açıklama |
|------|----------|
| OAuth yok + Gmail | “Google ile Bağlan” yalnızca `gmail_oauth_configured: true` iken görünür. Aksi halde App Password + IMAP gerekir. |
| HA image güncellemesi | Eski image’da 503/redirect ve eski UI davranışı görülebilir; `config.yaml` sürümü ile image tag’i eşleşmeli. |
| ghcr.io | Paket **public** değilse Supervisor image çekemez (`ha supervisor logs`). |
| Sync “OAuth credentials not configured” | Hesap `oauth_gmail` ile kayıtlı ama add-on’da Client ID/Secret yok. Hesabı sil, App Password ile yeniden ekle. |

## Geliştirici notları

- `POST /api/mail-accounts` — `MailAccountCreateRequest`; şifre modunda `imap_password` zorunlu.
- Health: `gmail_oauth_configured` — `GMAIL_OAUTH_CLIENT_ID` ve `SECRET` (veya built-in env) dolu mu.

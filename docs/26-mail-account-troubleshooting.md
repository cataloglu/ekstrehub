# Mail hesabı ekleme — bilinen sorunlar ve denetim listesi

## Ingress / siyah ekran 404 (1.0.20)

- **Semptom:** HA panelde add-on açılınca siyah alanda `404: Not Found` (veya boş sayfa).
- **Neden:** Ingress arkasında add-on’a çoğu zaman `GET /` gider; `X-Ingress-Path` yoksa sunucunun `<base href>` üretmesi **yanlış** kalır (`/` → asset’ler `/assets/...` olur). Ayrıca `.../app/<slug>` sonunda `/` yoksa göreli `./assets` yanlış çözülür.
- **Çözüm:** `index.html` içinde (build’de Vite ile) **tarayıcıdaki** `location.pathname` ile `<base href>` atanır; HA topluluğunda (Frigate, X-Ingress-Path tartışmaları) önerilen model.

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

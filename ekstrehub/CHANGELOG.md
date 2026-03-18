# EkstreHub Changelog

## 1.0.14 (2026-03-17)

### Düzeltmeler
- **422 hatası**: Hesap eklerken doğrulama hatası (eksik alan) artık anlamlı gösteriliyor (örn. "E-posta adresi: Field required")
- **Hesap Ekle** butonu: E-posta veya şifre boşken devre dışı (Gmail App Password ile)

---

## 1.0.13 (2026-03-17)

### Yenilikler
- **Mail hesabı silme**: Mail & Sync → hesabı seç → altta **Bu mail hesabını sil** (onay penceresi)

---

## 1.0.12 (2026-03-17)

### Düzeltmeler
- Gmail + OAuth yokken sadece "Şifre / Uygulama Şifresi" gösteriliyor; OAuth hesabı yanlışlıkla oluşturulmuyor
- Hesap eklerken (Gmail, OAuth yok) her zaman password modu kullanılıyor

---

## 1.0.11 (2026-02-21)

### Düzeltmeler
- **Gmail OAuth refresh hatası**: Token süresi dolunca net mesaj + "Hesabı silip yeniden ekleyin" (App Password veya Google ile Bağlan)
- **Hata mesajları**: API `detail` yanıtı artık UI’da gösteriliyor; sync/IMAP hataları sebebiyle birlikte gösteriliyor
- **Gmail App Password**: Şifre/e-posta trim, uygulama şifresindeki boşluklar kaldırılıyor; IMAP’ı açma linki eklendi

---

## 1.0.10 (2026-02-21)

### Yenilikler
- **Gmail OAuth — kullanıcı Client ID/Secret girmek zorunda değil**: Add-on yöneticisi tek OAuth client + redirect proxy ayarlarsa kullanıcılar sadece "Google ile Bağlan"a tıklar
- Yerleşik client desteği: `ekstrehub_builtin_gmail_client_id` / `ekstrehub_builtin_gmail_client_secret` ve `oauth_redirect_proxy_url` ile tek tık OAuth
- OAuth redirect proxy script'i: `scripts/oauth_redirect_proxy.py` (tek sabit redirect URI için)

---

## 1.0.9 (2026-03-21)

### Düzeltmeler
- **Gmail OAuth**: Referer header fallback — proxy header'ları yoksa (HA Ingress) sayfa URL'sinden redirect_uri oluşturuluyor

---

## 1.0.8 (2026-03-21)

### Düzeltmeler
- **Gmail OAuth (HA Ingress)**: redirect_uri artık X-Forwarded-Host, X-Forwarded-Proto ve X-Ingress-Path header'larından doğru oluşturuluyor — localde çalışan OAuth artık HA'da da çalışır
- OAuth callback sonrası yönlendirme ingress path'e göre yapılıyor
- `/api/oauth/gmail/redirect-uri` endpoint'i: Google Cloud Console'a eklenecek URI'yi gösterir

---

## 1.0.7 (2026-03-21)

### Düzeltmeler
- **OAUTH_NOT_CONFIGURED**: Gmail OAuth yapılandırılmamışsa artık net mesaj + App Password alternatifi gösteriliyor
- Gmail için "Şifre / Uygulama Şifresi" (App Password) seçeneği eklendi — OAuth olmadan da Gmail bağlanabilir
- Health API: `gmail_oauth_configured` alanı eklendi
- DOCS.md: Gmail OAuth kurulum rehberi eklendi

---

## 1.0.6 (2026-03-21)

### Düzeltmeler
- **404 hatası (HA Ingress)**: `X-Ingress-Path` header kullanılarak index.html'e `<base href>` enjekte ediliyor — tüm API ve asset path'leri artık doğru çözümleniyor
- Frigate, motionEye gibi add-on'lardaki kanıtlanmış yöntem uygulandı

---

## 1.0.5 (2026-03-21)

### Düzeltmeler
- **404 hatası giderildi**: HA Ingress alt path'te (örn. `/app/xxx`) Mail hesabı ekle / Google ile Bağlan tıklandığında 404 dönme sorunu çözüldü
- API çağrıları ve OAuth linki artık mevcut base path'e göre doğru çözümleniyor

---

## 1.0.4 (2026-03-21)

### Düzeltmeler
- Migration 0009: parse_status, parsed_json kolonları eklendi

---

## 1.0.3 (2026-03-21)

### HA Uyumluluk
- /data path fix, config.yaml iyileştirmeleri

---

## 1.0.2 (2026-03-21)

### Düzeltmeler
- SQLite uyumluluğu: `now()` → `CURRENT_TIMESTAMP`, PostgreSQL regex kaldırıldı
- SQLite batch_alter_table: 0005, 0006, 0007, 0008 constraint/index değişiklikleri
- İlk kurulumda syntax error ve OperationalError giderildi

---

## 1.0.1 (2026-03-21)

### Düzeltmeler
- Alembic migration 0008 `down_revision` düzeltildi — ilk kurulumda KeyError giderildi
- Add-on artık düzgün başlıyor

---

## 1.0.0 (2026-03-08)

### İlk Sürüm
- Gmail IMAP üzerinden otomatik ekstre indirme
- AI ile PDF/CSV parse (OpenAI, Ollama, custom LLM)
- Çoklu Gmail hesabı, otomatik sync
- Ekstre listesi, global arama, kategori analizi
- Home Assistant Ingress desteği

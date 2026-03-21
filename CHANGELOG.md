# Changelog

## [1.0.33] – 2026-03-21

### Improvements
- Mail UI: toggle UNSEEN-only vs scan last N; fetch limit selector; troubleshooting doc for zero scanned.

---

## [1.0.32] – 2026-03-21

### Fixes
- Auto-sync scheduler: fix `MailIngestionService` factory and call `run_sync()` (was broken after service constructor change).

---

## [1.0.31] – 2026-02-21

### Improvements
- Logs tab: show error if activity API fails; empty-state help; mail sync rows include account id/label/email and notes.

---

## [1.0.30] – 2026-02-21

### Improvements
- Mail & Sync: Mac Mail vs EkstreHub OAuth / app password copy.

---

## [1.0.29] – 2026-02-21

### Documentation
- Gmail OAuth: official Google links, Mac Mail vs third-party explanation.

---

## [1.0.28] – 2026-02-21

### Düzeltmeler
- Gmail: no fake OAuth link when Client ID/Secret missing (no redirect back to HA).

---

## [1.0.27] – 2026-02-21

### İyileştirmeler
- Gmail OAuth prompt select_account; UI copy clarifies Google-hosted sign-in.

---

## [1.0.26] – 2026-02-21

### Düzeltmeler
- Gmail OAuth: fix `window.open` noopener null bug (Google login not opening).

---

## [1.0.25] – 2026-02-21

### İyileştirmeler
- Gmail IMAP auth errors: user-facing Turkish message; UI copy for app password.

---

## [1.0.24] – 2026-02-21

### Düzeltmeler
- Gmail OAuth not_configured redirect: trailing slash before query (HA ingress 404 fix).

---

## [1.0.23] – 2026-02-21

### Düzeltmeler
- Gmail OAuth button: open in new tab with fallback (HA iframe).

---

## [1.0.22] – 2026-02-21

### Düzeltmeler
- Ingress: mutlak asset URL rewrite + Referer fallback for stripped `X-Ingress-Path`.

---

## [1.0.21] – 2026-02-21

### Düzeltmeler
- HA Ingress: `<base href>` = `X-Ingress-Path` (`/api/hassio_ingress/{token}/`), not browser `/app/...`.

---

## [1.0.20] – 2026-02-21

### Düzeltmeler
- HA Ingress: `<base href>` tarayıcıda `location.pathname` (Vite plugin); sunucu path’i artık tek başına kullanılmıyor.

---

## [1.0.19] – 2026-02-21

### Düzeltmeler
- HA Ingress: siyah ekran / `404` — her zaman `<base href>`; Gmail OAuth linki `<base>` ile uyumlu.

---

## [1.0.9] – 2026-03-21

### Düzeltmeler
- Gmail OAuth: Referer fallback ile redirect_uri (proxy header yoksa)

---

## [1.0.8] – 2026-03-21

### Düzeltmeler
- **Gmail OAuth (HA Ingress)**: redirect_uri X-Forwarded-* ve X-Ingress-Path ile doğru oluşturuluyor
- OAuth callback redirect'leri ingress path'e göre
- `/api/oauth/gmail/redirect-uri` — Google'a eklenecek URI'yi gösterir

---

## [1.0.7] – 2026-03-21

### Düzeltmeler
- **OAUTH_NOT_CONFIGURED**: Gmail OAuth yapılandırılmamışsa net mesaj + App Password alternatifi
- Gmail için App Password seçeneği — OAuth olmadan Gmail bağlanabilir
- Health API: `gmail_oauth_configured` alanı
- DOCS.md: Gmail OAuth kurulum rehberi

---

## [1.0.6] – 2026-03-21

### Düzeltmeler
- **404 hatası (HA Ingress)**: `X-Ingress-Path` header kullanılarak index.html'e `<base href>` enjekte ediliyor — tüm API ve asset path'leri artık doğru çözümleniyor
- Frigate, motionEye gibi add-on'lardaki kanıtlanmış yöntem uygulandı

---

## [1.0.5] – 2026-03-21

### Düzeltmeler
- **404 hatası giderildi**: HA Ingress alt path'te (örn. `/app/xxx`) Mail hesabı ekle / Google ile Bağlan tıklandığında 404 dönme sorunu çözüldü
- API çağrıları ve OAuth linki artık mevcut base path'e göre doğru çözümleniyor

---

## [1.0.4] – 2026-03-21

### Düzeltmeler
- **Migration 0009**: `statement_documents` tablosuna `parse_status` ve `parsed_json` kolonları eklendi
- `no such column: statement_documents.parse_status` hatası giderildi

---

## [1.0.3] – 2026-03-21

### HA Uyumluluk
- **/data path**: app_settings.json ve auto_sync_settings.json artık `/data/` altında doğru kaydediliyor
- **config.yaml**: ports, ports_description, HA developer docs referansı
- **build.yaml**: image source URL düzeltildi
- **translations**: network bölümü kaldırıldı (uyumsuz format)

---

## [1.0.2] – 2026-03-21

### Düzeltmeler
- **SQLite uyumluluğu**: Tüm migration'larda `now()` → `CURRENT_TIMESTAMP`, PostgreSQL regex (`~`) kaldırıldı
- İlk kurulumda `sqlite3.OperationalError: near "(": syntax error` hatası giderildi

---

## [1.0.1] – 2026-03-21

### Düzeltmeler
- **Alembic migration**: 0008 `down_revision` düzeltildi — `0007_add_mail_account_oauth_fields` referansı eklendi (KeyError: '0007' hatası giderildi)
- Add-on ilk kurulumda artık düzgün başlıyor

### Teknik
- GitHub Actions: Release event desteği — tag oluşturulunca doğru versiyonla build alınır

---

## [1.0.0] – 2026-03-08

### İlk Sürüm

#### Özellikler
- Gmail IMAP üzerinden otomatik ekstre indirme (App Password + OAuth 2.0)
- PDF/CSV ekstre parse — AI-first (OpenAI / Ollama / custom LLM)
- Birden fazla Gmail hesabı desteği
- Otomatik mail kontrolü (scheduler: her 5 dk → 8 saat arası)
- Ekstre listesi: banka bazlı gruplama, ödenmemiş/ödenmiş ayrımı
- Global arama: tüm kartlardaki işlemleri aynı anda ara
- İşlem kategorileri: Garanti BBVA standardında 28 kategori
- Masraf tespiti: BSMV, KKDF, yıllık ücret, gecikme faizi vb.
- Sistem Logları sayfası: mail sync ve parse geçmişi
- Home Assistant Ingress desteği
- Kalıcı veri: `/data/ekstrehub.db` güncelleme sonrası silinmez

#### Teknik Notlar
- **Veri güvenliği**: Tüm kullanıcı verileri `/data/` dizininde tutulur.  
  Add-on güncellemeleri veri silmez — sadece kümülatif (additive) DB  
  migrasyonları çalıştırılır.
- **Desteklenen mimariler**: `amd64`, `aarch64`, `armv7`
- **Python**: 3.12, **Node.js**: 20 (build only)
- **LLM**: OpenAI `gpt-4o-mini` (varsayılan), Ollama veya custom API

---

> **Güncelleme notları (gelecek sürümler için):**  
> Veritabanı şeması değişiklikleri her zaman kümülatiftir (ADD COLUMN, CREATE TABLE).  
> Mevcut veriler hiçbir zaman silinmez.  
> `/data/` dizinine yazılan dosyalar (veritabanı, ayarlar) HA tarafından korunur.

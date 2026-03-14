# Changelog

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

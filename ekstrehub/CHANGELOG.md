# EkstreHub Changelog

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

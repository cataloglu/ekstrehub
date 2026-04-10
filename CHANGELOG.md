# Changelog

## [1.0.64] – 2026-04-04

### Features
- **Loyalty dashboard totals**: Dashboard now aggregates remaining points/miles value from existing statements and shows a per-card/program summary in one view.
- **Reminder enrichment**: Loyalty reminders now include structured fields (`loyalty_program`, `remaining_value_try`) extracted from statement text.

---

## [1.0.63] – 2026-04-04

### Features
- **One-click cleanup for existing bad parses**: Added an AI Parser action that re-runs only suspicious non-card statement rows (max 50) and auto-cleans items reclassified as `non_credit_card_document`.

---

## [1.0.62] – 2026-04-04

### Fixes
- **Non-credit-card PDF rejection**: Parser now detects investment/dekont-style documents (e.g. “İşlem Sonuç Formu”, fund buy/sell slips) and marks them as non-credit-card instead of parsing them as card statements.
- **Reparse UX clarity**: Reparse returns a dedicated `non_credit_card_document` error for these files and UI shows a clear explanation.

---

## [1.0.61] – 2026-04-04

### Fixes
- **Reparse double-submit guard**: Statement reparse action is now locked while an existing reparse is running, preventing overlapping requests and false UI error states.

---

## [1.0.60] – 2026-04-04

### Features
- **HA sensor statement details**: New statement notifications now include per-statement `due_date` and `total_debt` details in sensor attributes (`statement_details`, `latest_due_date`, `latest_total_debt`).

### Fixes
- **Reminder noise reduction**: Statement reminder extraction now skips generic account header blocks and card detail view shows only loyalty points/miles expiry reminders.

---

## [1.0.59] – 2026-04-04

### Fixes
- **HA notifier authorization**: Add-on now explicitly requests Home Assistant/Supervisor API access (`homeassistant_api`, `hassio_api`) so sync notifications can post without `401 Unauthorized`.
- **Actionable notifier logs**: `ha_notify_failed` now logs HTTP status/body and a clear hint when authorization is missing.

---

## [1.0.58] – 2026-04-04

### Fixes
- **Points/miles expiry accuracy**: Reminder extraction now scores dates by local context and excludes statement header dates (`Hesap Kesim`, `Son Ödeme`, `Dönem Borcu`) from loyalty expiry detection.
- **Expiry classification tightened**: Entries are marked `expiry` only when explicit expiry/deadline cues exist, reducing false positives in “Puan / Mil” dashboard items.

---

## [1.0.57] – 2026-04-03

### Features
- **Dashboard reminders simplified**: “Puan / Mil” panel now shows only spend-before-expiry points/miles items; non-points legal/service reminders are removed from this section for cleaner focus.

---

## [1.0.56] – 2026-03-31

### Fixes
- **Parser timeout resilience**: LLM timeout now triggers one automatic retry with increased timeout before marking the statement as failed.
- **Observability**: Successful second attempt is marked with `llm_retry_success` parse note for easier troubleshooting.

---

## [1.0.55] – 2026-03-31

### Features
- **Home Assistant automatic notifications**: When new statements are saved, EkstreHub now pushes `persistent_notification.create` and updates `sensor.ekstrehub_new_statements` + `sensor.ekstrehub_last_sync` through HA Supervisor API (no manual webhook needed).
- **Works for both sync paths**: Notification flow is triggered after manual `/api/mail-ingestion/sync` and background auto-sync runs.

### Fixes
- **Legacy DB learned-rules resilience**: Missing `learned_parser_rules` table no longer breaks parsing flow; safe recovery path keeps statement ingestion running.

---

## [1.0.54] – 2026-03-31

### Fixes
- **Legacy DB compatibility**: Parser flow now tolerates missing `learned_parser_rules` table and continues parsing instead of dropping PDFs.
- **End-to-end verification**: Full mailbox re-sync + failed-only reparse path validated; final state is all documents parsed without pending/failed leftovers.

---

## [1.0.53] – 2026-03-24

### Fixes
- **Silent CSV data loss**: Failed CSV attachments now stored as `parse_failed` rows.
- **Content dedupe false positive**: Include `total_due_try` + `card_number` in duplicate filter.
- **LLM tx amount crash**: Use `_parse_float` with TR locale support + `round(2)`.
- **LLM truncation**: Page-aware (form-feed) splitting; brace-matching JSON repair.
- **PDF extraction**: Explicit `PDFExtractionError` for encrypted/corrupt/empty files.
- **Empty text short-circuit**: Skip LLM call for text < 50 chars.
- **is_llm_failure_empty**: All zero-transaction results now `parse_failed`.
- **Card regex window**: 3000 → 8000 chars.
- **Heuristic metadata**: Head+tail scan for long PDFs.
- **Parse validation**: Warnings for min>total, reversed dates, early due_date.
- **LLM prompt**: Anti-hallucination and consistency rules added.

---

## [1.0.52] – 2026-03-24

### Fixes
- **SQLite `database is locked`**: WAL, longer busy timeout, connection tuning; **single ingestion lock** so mail sync and batch re-parse never write concurrently.
- **İş Bankası / Maximiles**: Stronger PDF text markers (`maximiles.com`, `MAXIMIL`, `0850 724`, etc.) before POS “Param” heuristics.

### Features
- **Statements UI**: Per-row **Bank** dropdown for manual correction (matches `PATCH /api/statements/{id}/bank`).

---

## [1.0.51] – 2026-02-21

### Fixes
- **Öğrenilmiş regex tek başına dönem/tarih doldurmuyordu** — LLM açıksa artık her zaman tam LLM parse (dönem, son ödeme, tutar, kart). Regex sadece LLM kapalıyken veya LLM hata verince yedek işlem satırları olarak kalır; LLM düşerse öğrenilmiş işlemler + PDF heuristik ile tarih/tutar doldurulur.

---

## [1.0.50] – 2026-02-21

### Fixes
- **Yeniden çöz + yanlış Param bankası**: `parsed_json` içinde `Param` kalsa bile artık **e-posta bankası** (gerçek banka) öncelikli; Param/Papara ipucu yok sayılıp PDF’den `resolve_bank_hint` ile İş vb. tespit edilir. Learned-rules anahtarı da Param’a kilitlenmez.
- **Reparse sessiz başarısızlık**: Mail hesabı olmayan ekstreler için sonuçta `email_or_account_missing` dönülür; UI’da Türkçe açıklama.

---

## [1.0.49] – 2026-02-21

### Features
- **Özet** sekmesi: **Puanlar & hatırlatmalar** paneli — Pazarama / MaxiMil ve son kullanma tarihli tüm aktif bildirimler tek listede; son tarihe göre sıralı, 30 gün içinde kırmızı vurgu, **Aç** ile ilgili ekstre genişletilir. KPI kartı: aktif hatırlatma sayısı (tıklayınca listeye kaydırır).

---

## [1.0.48] – 2026-02-21

### Features
- **Ekstre hatırlatmaları**: PDF metninden Pazarama / MaxiMil son kullanma, asgari ödeme uyarısı, sözleşme / Üstü Kalsın bildirimleri gibi bloklar çıkarılır (`statement_reminders` in `parsed_json`). API `GET /api/statements` yanıtına dahil; **Ekstreler** kartında 📌 rozet + açılınca liste (tarih geçince soluk).

---

## [1.0.47] – 2026-03-22

### Features
- **Dosyalar** tab: all ingested PDF/CSV attachments with parse status (totals: success / failed / pending). Filter: all / non-parsed / parsed / parse_failed. API: `GET /api/ingestion/documents`, `GET /api/ingestion/documents/stats`.
- Sidebar badge on **Dosyalar** when `non_parsed > 0`.

---

## [1.0.46] – 2026-03-22

### Features
- **Original PDF**: `GET /api/statements/{id}/pdf` — streams PDF from IMAP (same as reparse). UI: Ekstreler → **Orijinal PDF** (new tab).

### Fixes
- **Param false positive**: `param` substring matched inside words like *parametre*; bank detection now requires whole word `\bparam\b`.

### Improvements
- LLM prompt: `bank_name` must be the card-issuing bank, not payment-wallet names (Param, Paycell, …).

---

## [1.0.45] – 2026-03-22

### Features
- **Posta önbelleği (`POSTA`)**: `POST /api/system/clear-email-ingestion-cache` — deletes `statement_documents`, `emails_ingested`, `mail_ingestion_runs` so the same IMAP messages can be ingested again. Learned rules + audit log preserved (unlike `SIFIRLA`). Settings → System → “Posta önbelleğini temizle”.

### Why
- Deleting statements only leaves `emails_ingested.message_id` rows; sync skips every message as duplicate.

---

## [1.0.44] – 2026-03-22

### Fixes
- Bank name: LLM sometimes returns the string `"null"` (truthy); merge with email/PDF hints was skipped — normalized + canonical names (`app/ingestion/bank_identification.py`). API list/activity coalesces legacy stored values.
- Email bank profiles use Turkish display names (`İş Bankası`, `Yapı Kredi`); learned rules lookup supports legacy DB keys.

### Tests
- `tests/test_bank_identification.py`: normalization, LLM null merge, learned-rule keys.

---

## [1.0.43] – 2026-03-21

### Fixes
- Activity log includes `parse_notes` for failed parses (was only loaded for `parsed` status).

---

## [1.0.42] – 2026-03-21

### Improvements
- Logs tab: table / plain / cards; TSV export; clipboard fallback for HA.

---

## [1.0.41] – 2026-03-21

### Improvements
- Parser diagnostic logs: `text_fp`, parse path, `learned_skip` reasons, LLM request sizes.

---

## [1.0.40] – 2026-03-21

### Features
- Settings → System: **Clear learned regex rules** (confirm `KURALLAR`); `POST /api/system/clear-learned-rules`.

---

## [1.0.39] – 2026-03-21

### Fixes
- LLM timeout default 180s; `parse_failed` + reparse `ok:false` on timeout/failure; learned rules save if regex matches ≥1 line.

---

## [1.0.38] – 2026-03-21

### Features
- Settings → **System**: typed confirmation (`SIFIRLA`) to wipe ingestion data (statements, emails, runs, learned rules, audit logs); mail accounts & LLM settings kept.

---

## [1.0.37] – 2026-03-21

### Features
- Statements tab: per-PDF **Re-parse** and bulk **Re-parse selected** (IMAP re-fetch + LLM).

---

## [1.0.36] – 2026-03-21

### Features
- Learned per-bank regex rules after LLM success; local parse skips API when rules match. Env `EKSTREHUB_DISABLE_LEARN_RULES=1` disables training.

---

## [1.0.35] – 2026-03-21

### Fixes
- Sequential re-parse requests (avoid ingress/browser timeout); OpenAI default LLM timeout 180s.

---

## [1.0.34] – 2026-03-21

### Features
- Bulk re-parse PDF statements via API + Settings → AI Parser buttons (after enabling LLM).

---

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

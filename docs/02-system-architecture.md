# System Architecture

## Operating Model

Sistem online calisir ve merkezi bir backend uzerinden servis edilir. Banka sistemlerine dogrudan baglanmaz; kullanicinin belirledigi mail kutusuna gelen ekstre mailleri islenir.

## High-Level Components

- `api-gateway`: UI ve entegrasyonlar icin HTTP API
- `mail-ingestor`: IMAP ile yeni mailleri tarar ve attachment alir
- `document-processor`: PDF/image normalize eder ve OCR'a hazirlar
- `ocr-service`: lokal OCR motoru (birincil + fallback)
- `statement-extractor`: parser + AI ile alan cikarimi yapar
- `parser-registry`: parser versiyonlarini ve kural setlerini tutar
- `approval-service`: parser drift durumlarinda onay sureci yonetir
- `reporting-service`: aylik raporlar ve ozet metrikler uretir
- `notification-service`: son odeme ve aidat uyarilari
- `db`: operasyonel veri depolama
- `object-storage` (opsiyonel): ham dosya saklama

## Main Data Flow

1. `mail-ingestor` yeni maili alir ve uygun eki secerek is kuyruğuna yollar.
2. `document-processor` dosyayi normalize eder.
3. `ocr-service` metin cikarir.
4. `statement-extractor` temel alanlari cikarir:
   - statement period
   - total debt
   - minimum payment
   - due date
   - fee-related entries
5. Validasyon adimi tutarlilik kontrolu yapar.
6. Sonuc guvenli ise `statements` tablolarina yazilir.
7. Drift varsa `parser_change_requests` kaydi olusur ve kullanici onayi beklenir.
8. `reporting-service` ozetleri hesaplar; UI bu verileri gosterir.

## Deployment Profiles

- Standalone Docker: hizli gelistirme ve test
- Home Assistant Add-on: HA icinde panel + entity yayini

UI tarafinda primary hedef Home Assistant Ingress'tir. Ayni UI standalone modda da calisir ancak tasarim ve UX kararlarinda Ingress icinde mobil kullanim onceklidir.

Not: Her iki mod da ayni is mantigi servislerini kullanir.

## Security Baseline

- Tam kart numarasi tutulmaz; sadece son 4 hane
- CVV/PIN/sifre benzeri veri asla alinmaz
- Mail sifreleri ve gizli bilgiler secret store'da tutulur
- Audit log ile parser degisiklik ve onay kararlarinin izi saklanir

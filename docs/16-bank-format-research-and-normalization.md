# Bank Format Research and Normalization

## Scope

Bu dokuman, banka kredi karti ekstrelerinin PDF/CSV formatlarinda parser tasarimi icin minimum ortak alanlari ve normalize stratejisini tanimlar.

## Common Fields (PDF Statements)

Arastirma ve banka bilgilendirme iceriklerinden hareketle, cogu ekstreden beklenen cekirdek alanlar:

- statement period (donem baslangic / bitis)
- statement date
- due date (son odeme tarihi)
- total debt / period debt
- minimum payment
- card last4 (veya maskeleme)
- transaction rows (islem tarihi, aciklama, tutar)
- fee-like rows (aidat/gecikme/faiz benzeri kalemler)

## Common Fields (CSV Exports / API-like feeds)

CSV veya yapilandirilmis ekstre ciktilarinda sik gorulen kolonlar:

- transaction date/time
- description
- amount
- currency (bazi bankalarda statement-level)
- card identifier (masked)
- installment or remaining installment (opsiyonel)
- reward/point alanlari (opsiyonel)

## Normalization Contract (v0)

Parser ciktilari asagidaki normalize alana map edilmelidir:

- `period_start`, `period_end`
- `due_date`
- `total_debt`, `minimum_payment`
- `currency` (sistem para birimi daima `TRY`)
- `original_currency` (islem kaynagi USD/EUR vb ise opsiyonel metadata)
- `transactions[]`:
  - `tx_date`
  - `description`
  - `amount`
  - `type` (`spend|fee|interest|other`)

## Drift Sources

- Baslik isimlerinin banka ve dile gore degismesi
- Tarih ve tutar formatlari (`dd.mm.yyyy`, `yyyy-mm-dd`, `1.234,56`)
- Aidat/faiz benzeri kalemlerin farkli aciklamalarla gecmesi
- PDF icinde tablo yapisinin farkli sayfa duzenlerinde gelmesi

## Parsing Strategy

1. Header-first extraction (due date, minimum payment, total debt)
2. Transaction table extraction
3. Fee keyword + pattern detection
4. Cross-check:
   - total debt tutarliligi
   - due date parse confidence
5. Confidence score + review route

## Dataset Plan (Phase 1 Input)

- Her banka icin en az 10 anonimlestirilmis PDF
- Mümkünse 2-3 CSV ornegi
- Beklenen cikti JSON fixture
- Zorunlu varyasyon:
  - farkli aylar
  - aidatli/aidatsiz donem
  - taksitli islem iceren ekstre

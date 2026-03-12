# Test Strategy

## Test Pyramid

- Unit tests: parser, validation, fee classification, date/amount normalization
- Integration tests: mail ingestion -> OCR -> extraction -> persistence
- End-to-end tests: dashboard/reporting ve parser approval user flow

## Critical Scenarios

1. Ayni mailin tekrar islenmesi duplicate kayit olusturmamali
2. Due date parse hatasi review_needed ile isaretlenmeli
3. Aidat kalemi dogru siniflanmali
4. Parser drift tespitinde pending approval olusmali
5. Reddedilen candidate parser active olmamali

## Golden Dataset

- Her desteklenen banka icin anonimlestirilmis ornek dokuman seti
- Her release oncesi bu set uzerinde regression calistirma
- Basari metrikleri release notuna islenmeli

## Quality Gates

- Unit test pass rate: %100 required
- Integration smoke: pass required
- Critical parser regression: 0 tolerance
- Lint/type checks: blocking

## Operational Testing

- IMAP baglanti timeout/retry testleri
- OCR fallback testi
- Queue backlog ve retry davranisi
- Notification deliverability smoke

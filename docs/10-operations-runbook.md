# Operations Runbook (MVP)

## Daily Checks

- Mail ingestion run status
- Parse success / review_needed oranlari
- Pending parser approvals
- Due-date alert generation durumu

## Incident Classes

- P1: Statement extraction tamamen durdu
- P2: Belirli banka parser'i bozuk
- P3: Rapor gecikmesi / bildirim gecikmesi

## First Response Steps

1. Son ingestion run logunu kontrol et
2. OCR servis sagligini kontrol et
3. Parser versiyon degisimi oldu mu bak
4. Queue'da birikme var mi kontrol et
5. Gerekirse onceki parser versiyonuna rollback yap

## Rollback Policy

- Parser rollback: son active parser'a don
- Service rollback: bir onceki stabil image tag
- DB rollback: destructive migration yoksa forward-fix tercih edilir

## SLO Draft

- Ingestion to visible statement: p95 < 5 dk
- Due-date alerts generated on time: >= %99
- Monthly report generation success: >= %99

## On-Call Notes

- P1/P2 olaylarinda parser approval akisi gecici dondurulebilir
- Kullaniciya incident aciklamasi maskeli veriyle yapilir

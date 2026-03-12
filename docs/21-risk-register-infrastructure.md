# Infrastructure Risk Register

## R1 - IMAP Throttling / Temporary Blocks

- Etki: Ingestion gecikmesi, eksik veri algisi
- Mitigation:
  - 15 dk polling baseline
  - unseen-only query
  - fetch limit
  - exponential backoff

## R2 - OCR Accuracy Variance (Banka format degisimi)

- Etki: kritik alanlarin yanlis parse edilmesi
- Mitigation:
  - confidence scoring
  - mandatory review queue for low confidence
  - golden dataset regression

## R3 - LLM Resource Exhaustion

- Etki: latency artisi, timeout
- Mitigation:
  - queue + concurrency limit
  - model keep-alive tuning
  - fallback extraction path

## R4 - DB Data Loss / Corruption

- Etki: statement gecmisi kaybi
- Mitigation:
  - gunluk backup
  - haftalik restore drill
  - WAL-based strategy (hardening phase)

## R5 - Secret Exposure

- Etki: IMAP account compromise
- Mitigation:
  - secrets at rest
  - masked logs
  - no plain secret in UI or docs

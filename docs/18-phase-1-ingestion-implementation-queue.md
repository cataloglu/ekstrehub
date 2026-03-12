# Phase 1 Ingestion Implementation Queue

## Objective

Mail -> PDF/CSV -> OCR -> extraction -> report akisini production'a hazirlayacak sira.

## Queue

1. Mail ingestion worker (IMAP poll + dedup)
2. Attachment classifier (PDF/CSV/image)
3. Document normalization (pdf split, rotate, quality checks)
4. OCR service integration (PaddleOCR primary, fallback path)
5. Structured extraction (rule + LLM hybrid)
6. Validation and confidence scoring
7. Fee/aidat detector v0
8. Persistence and report aggregation
9. Review queue + approval integration
10. Dashboard API binding

## CSV Track (Parallel)

- CSV parser adapter
- Column mapping presets (bank/profile bazli)
- Date/amount locale normalization

## Current Progress

- Item 1 baslatildi: IMAP ingestion service + `message_id` / `doc_hash` dedup iskeleti eklendi.
- Item 2 parcali hazir: attachment type siniflandirma (`pdf|csv|image|other`) eklendi.
- CSV track baslatildi: CSV parser adapter v0 ve date/amount normalize eklendi.
- Ingestion run izleme eklendi: `run_id` uretimi ve run detay endpoint iskeleti.
- Sender/subject bazli banka tahmini (profil baslangici) eklendi.
- Run list endpoint filtreleri eklendi: status + tarih araligi.
- IMAP retry/backoff politikasi ve env konfigi eklendi.

## Acceptance Gate

- Due date, total debt, minimum payment alanlarinda hedef accuracy
- Aidat tespit precision hedefi
- End-to-end p95 latency hedefi
- Review queue dogru tetikleniyor

# AI Model Selection and Deployment (Local-first)

## Goal

OCR + extraction hattinda dis API key bagimliligina girmeden, yerel veya kendi altyapinda calisabilecek model setini belirlemek.

## OCR Decision

Primary OCR:

- PaddleOCR (PP-OCRv5 + gerekirse PP-Structure)

Fallback OCR:

- Tesseract (yalin fallback)

Neden:

- Local deploy kolayligi
- Dokuman OCR ekosistemi olgun
- PDF/image akislari icin uygun arayuz

Not:

- Turkce performans banka formatina gore degisir; mutlaka kendi golden dataset ile olculmeli.

## Extraction LLM Decision (v0)

Primary local model:

- Qwen2.5 7B Instruct (Ollama uzerinden)

Alternative candidate:

- Llama 3.1 8B (yerel benchmark karsilastirmasi icin)

Neden:

- JSON tabanli structured output kabiliyeti
- Yerel calistirma kolayligi
- Makul model boyutu / latency dengesi

## Runtime Topology

- `ocr-service`: PaddleOCR container
- `llm-service`: Ollama + secili model
- `statement-extractor`: kural + LLM hybrid pipeline

## Prompt/Output Contract

LLM yalnizca belirlenen JSON schema'ya cikis verir:

- `due_date`
- `total_debt`
- `minimum_payment`
- `currency` (`TRY`)
- `original_currency` (opsiyonel, USD/EUR vb kaynak islem bilgisi)
- `transactions[]`
- `confidence`

Schema-disi cevaplar reject edilir.

## Benchmark Plan (Must-have before Phase 1 close)

Karsilastirilacak:

- OCR accuracy (field-level)
- End-to-end extraction accuracy
- p95 latency per document
- malformed JSON rate

Model karsilastirma seti:

- Qwen2.5 7B vs Llama 3.1 8B
- Ayni golden dataset ve ayni schema kurallari ile

## Promotion Policy

- Varsayilan model tek basina karar vermez.
- Low-confidence veya schema mismatch durumlari review queue'ya duser.
- Parser/model degisiklikleri approval akisiyla aktive edilir.

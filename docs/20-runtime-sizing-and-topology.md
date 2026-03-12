# Runtime Sizing and Topology

## Environments

- `dev`: tek host, docker compose
- `staging`: prod benzeri ama daha kucuk kaynak
- `prod`: HA add-on runtime + ayri DB/LLM/OCR servisleri

## Service Topology (Prod Target)

- `api-gateway` (FastAPI)
- `mail-ingestor` (worker)
- `document-processor`
- `ocr-service` (PaddleOCR)
- `llm-service` (Ollama)
- `postgresql`
- `redis` (queue/retry/caching; Phase 2)

## Minimum Resource Profile (Starting Point)

- API + worker: 2 vCPU / 2-4 GB RAM
- OCR service: 2 vCPU / 4 GB RAM
- LLM (Qwen2.5 7B quantized): 8-12 GB RAM baseline
- PostgreSQL: 2 vCPU / 4 GB RAM / SSD storage

Not: Bu degerler benchmark ile kesinlestirilir.

## Capacity Guardrails

- Polling batch size ve fetch limit ile IMAP load kontrolu
- LLM queue length threshold asiminda fallback/retry
- OCR timeout + retry policy
- API request timeout ve idempotent ingestion tasarimi

## Phase Mapping

- Phase 1: API + worker + DB + basic OCR
- Phase 2: LLM service tuning + queue governance
- Phase 3: autoscaling/prefetch/observability hardening

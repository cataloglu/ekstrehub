# Infrastructure Research Decisions

Bu dokuman, dis arastirma bulgularindan uretilmis uygulanabilir teknik kararlari icerir.

## 1) Home Assistant Add-on Decisions

Arastirma ozeti:

- Ingress-first calisma modeli guvenlik ve UX acisindan uygun.
- Secret degerleri add-on options icinde plain tutmak yerine secret mekanizmasi tercih edilmeli.
- Add-on verisi icin izolasyonlu klasor/persistence alani kullanilmali.

Karar:

- Ingress zorunlu, host port acma default kapali kalir.
- IMAP sifre/token bilgileri secret source'tan okunur.
- Add-on state/log dosyalari izole data volume'de tutulur.

## 2) Gmail / Outlook IMAP Polling Decisions

Arastirma ozeti:

- Gmail IMAP tarafinda gunluk bant/genislik limitleri vardir.
- Uzun sure acik baglantilar ve agresif polling throttling riskini artirir.
- Outlook/Exchange IMAP tarafi da throttling uygular.

Karar:

- Varsayilan polling araligi: 15 dakika.
- `UNSEEN` sorgusu default acik.
- Her poll'da fetch limiti uygulanir (`IMAP_FETCH_LIMIT`).
- Retries exponential backoff ile yapilir.
- Ayni mesaj tekrar indirilmez (`message_id` dedup).

## 3) OCR + LLM Runtime Decisions (Self-hosted)

Arastirma ozeti:

- PaddleOCR dokuman OCR icin olgun ve local deploy icin uygun.
- Qwen2.5 7B structured JSON extraction icin guclu aday.
- Ollama uretimde memory/concurrency limitleri explicit ayarlanmali.

Karar:

- OCR primary: PaddleOCR
- OCR fallback: Tesseract
- LLM primary: Qwen2.5 7B
- LLM benchmark candidate: Llama 3.1 8B
- Ollama runtime parametreleri environment ile kontrol edilir:
  - `OLLAMA_NUM_PARALLEL`
  - `OLLAMA_KEEP_ALIVE`
  - `OLLAMA_MODELS`

## 4) PostgreSQL Backup Decisions

Arastirma ozeti:

- Production tarafinda yalniz dump yeterli degildir.
- PITR hedefi icin WAL/continuous archiving gerekir.

Karar:

- MVP: gunluk logical backup + haftalik restore testi.
- Production hardening: pgBackRest tabanli full + WAL archive.
- Retention:
  - gunluk backup: 14 gun
  - haftalik full: 8 hafta
  - WAL: minimum 7 gun PITR penceresi

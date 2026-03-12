# Repository Structure (Target)

## Proposed Layout

```text
ekstrehub/
  app/                      # mevcut API bootstrap (gecis donemi)
  ui/                       # frontend
  docs/                     # mimari ve plan dokumanlari
  services/
    api-gateway/
    mail-ingestor/
    document-processor/
    ocr-service/
    statement-extractor/
    approval-service/
    reporting-service/
    notification-service/
  shared/
    contracts/
    libs/
  infra/
    docker/
    migrations/
    observability/
```

## Transitional Note

Su an repo minimal iskelette oldugu icin `app/` aktif tutulur. Servislesme adim adim yapilir; once en kritik akislardan baslanir (`mail-ingestor`, `statement-extractor`, `approval-service`).

## Ownership Suggestion

- `services/*`: business capability ownership
- `shared/contracts`: service API schema ownership
- `infra/*`: deployment and ops ownership

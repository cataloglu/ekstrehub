# Phase 0 Execution Backlog

Bu dokuman, "Foundation" fazini uygulanabilir gorevlere boler.

## Sprint Window

- Hedef sure: 5-7 gun
- Faz amaci: kod tabanini guvenli sekilde MVP gelistirmesine hazirlamak

## Progress Snapshot

- Completed: P0-1, P0-2, P0-3, P0-4, P0-5, P0-6, P0-9, P0-10
- In progress: P0-7 (Golden Dataset Prep)
- Next up: P0-8 (CI Starter Pipeline)

## Task List

## P0-1: Runtime and Environment Baseline

- Priority: P0
- Estimate: 0.5 gun
- Scope:
  - Python ve Node surumlerini netlestir
  - `.env.example` genislet (imap, db, app, security)
  - `docker-compose.yml` profile yaklasimi belirle (api, db, worker)
- Acceptance:
  - Proje tek komutla lokal kalkabiliyor
  - Eksik env degiskenleri startup'ta net hata veriyor

## P0-2: Config and Secrets Strategy

- Priority: P0
- Estimate: 0.5 gun
- Scope:
  - Config katmani standardi (env -> app config)
  - Secret alanlari listesi ve nerede tutulacagi
  - Secret masking policy
- Acceptance:
  - Config kaynagi tek bir pattern ile okunuyor
  - Hassas alanlar loglarda maskeleniyor

## P0-3: Database Foundation

- Priority: P0
- Estimate: 1 gun
- Scope:
  - DB secimi final (PostgreSQL onerilir)
  - Migration araci secimi
  - Ilk migration: `users`, `cards`, `statements`, `parser_versions`, `parser_change_requests`
- Acceptance:
  - Sifirdan DB ayağa kaldirilip migration uygulanabiliyor
  - Migration rollback/forward policy dokumante

## P0-4: Logging, Audit, and Observability Baseline

- Priority: P0
- Estimate: 0.5 gun
- Scope:
  - Structured log formati
  - Correlation/request id standardi
  - Audit log temel modeli
- Acceptance:
  - Her API istegi trace edilebilir id ile loglaniyor
  - Kritik aksiyonlar audit tablosuna yaziliyor

## P0-5: Auth and Access Decision (MVP-safe)

- Priority: P1
- Estimate: 0.5 gun
- Scope:
  - MVP auth modeli netlestirme (single-user secure token/session)
  - Parser approval endpoint yetki kurali
- Acceptance:
  - Korumali endpointler auth olmadan erisilemez
  - Approval aksiyonlari yetkisiz calismaz

## P0-6: API Contract Freeze v0

- Priority: P1
- Estimate: 0.5 gun
- Scope:
  - `docs/07-api-contracts.md` endpointlerinin v0 freeze edilmesi
  - Error code katalogu olusturma
- Acceptance:
  - Frontend/backend ayni contract ile calisacak durumda
  - Hata kodlari standart formatta

## P0-7: Golden Dataset Prep (Minimal)

- Priority: P1
- Estimate: 1 gun
- Scope:
  - 2-3 banka icin anonimlestirilmis ornek dokuman seti
  - Beklenen parse ciktisi fixture'lari
- Acceptance:
  - Parser regression testleri bu dataset ile kosabiliyor
  - Dataset versiyonlanmis ve dokumante

## P0-8: CI Starter Pipeline

- Priority: P1
- Estimate: 0.5 gun
- Scope:
  - Lint + test + basic build adimlari
  - Fail-fast policy
- Acceptance:
  - PR acildiginda temel quality gate kosuyor
  - Kirmizi/yasil sonuc net gorunuyor

## P0-9: Home Assistant Compatibility Check

- Priority: P2
- Estimate: 0.5 gun
- Scope:
  - `config.yaml` ve add-on bootstrap uyum kontrolu
  - Ingress panel acilis smoke senaryosu
  - HA best-practice checklist dokumani ile standartlastirma
- Acceptance:
  - Add-on metadata valid
  - Standalone + HA modlarinda conflict yok
  - `docs/14-home-assistant-integration-best-practices.md` guncel

## P0-10: Documentation Hardening

- Priority: P1
- Estimate: 0.5 gun
- Scope:
  - Tum docs'larda terminoloji birligi
  - "out of scope" alanlarini netlestirme
  - AGENTS + rules ile tutarlilik kontrolu
- Acceptance:
  - Ekibin tek kaynaktan onboarding yapabildigi net bir set var

## Dependency Order

1. P0-1 -> P0-2 -> P0-3
2. P0-4 paralel ilerleyebilir
3. P0-5 ve P0-6, P0-3 uzerine
4. P0-7, P0-6 ile birlikte
5. P0-8, P0-1/P0-3 tamamlaninca
6. P0-9 ve P0-10 kapanis adimi

## Definition of Done (Phase 0)

- Lokal ortam tek komutla kalkiyor
- DB migration altyapisi calisir durumda
- Auth + audit minimum guvenlik seviyesinde aktif
- API contract v0 freeze
- CI temel kalite kapilari aktif
- Phase 1'e gecis icin riskler dokumante ve kabul edilmis

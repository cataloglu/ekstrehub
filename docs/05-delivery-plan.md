# Delivery Plan

## Phase 0 - Foundation (Week 1)

- Monorepo klasor yapisini netlestir
- Ortak config, logging ve env stratejisini belirle
- DB migration altyapisini sec
- Basic auth ve user bootstrap kararlarini netlestir

Exit criteria:

- Mimari dokumanlari onayli
- Calisan local docker gelistirme ortami

## Phase 1 - MVP Core (Weeks 2-4)

- IMAP mail ingestion
- Attachment extraction + OCR pipeline
- Statement extraction + temel validasyon
- Dashboard API + ilk UI gorunumu (Ingress-first, mobile-first)
- Aidat tespit ve son odeme alarmlari

Exit criteria:

- Gercek maillerden statement kaydi uretiliyor
- Dashboard'da kart bazli borc ve due date gorunuyor

## Phase 2 - Reliability and Parser Governance (Weeks 5-6)

- Parser version registry
- Drift detection + approval workflow
- Candidate parser test harness
- Audit ve gozlemlenebilirlik metrikleri

Exit criteria:

- Parser farklari pending onaya dusebiliyor
- Approved/rejected akisi production-safe

## Phase 3 - Reporting and Product Hardening (Weeks 7-8)

- Aylik rapor motoru
- Fee trend analizleri
- Bildirim iyilestirmeleri
- Performance and security hardening

Exit criteria:

- Aylik raporlar duzenli uretiliyor
- Kritik akislarda hata orani hedef altinda

## Planned Backlog (Post-MVP)

- MQTT entegrasyonu
- Home Assistant entity publish iyilestirmeleri
- Coklu mail kutusu
- Gelişmis kategori modelleme

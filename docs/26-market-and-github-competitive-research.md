# Market and GitHub Competitive Research

## Scope

Global (EN) ve Turkiye (TR) tarafinda benzer urunlerin ne yaptigi, bizim urunun nerede ayrisacagi.

## Global Product Patterns

Pazar gozlemi (Rocket Money, Monarch, benzeri bill trackers):

- Coklu hesap ve due-date takibi var.
- Subscription/recurring gider takibi guclu.
- Bazi urunlerde annual fee/bill alerts var.
- Genelde banka baglantisi aggregation tabanli (US-centric).
- PDF/ekstre parser + parser drift onay akisi cogu urunde ana odak degil.

## Turkey-Focused Observation

- Turkiye'de bankalarin kendi uygulamalari kendi kartlari icin guclu.
- Ucuncu parti finance app'ler var ama:
  - banka-ozel format parser governance derinligi sinirli,
  - ekstre PDF/CSV ingestion + aidat tespit odagi net degil.
- Coklu kart ve bankalar arasi tek panel ihtiyaci halen acik.

## Open Source / GitHub Landscape

Benzer yondeki acik kaynak yaklasimlar:

- E-posta parsing tabanli harcama cikarma projeleri
- PDF->CSV donusum araclari
- OCR tabanli statement parser denemeleri

Gorulen bosluk:

- Uretim kalitesinde parser versiyonlama + kullanici onayli drift yonetimi
- TR banka formatlari icin operasyonel kalite ve surekli regression
- Home Assistant ingress-first, self-hosted odakli finans paneli

## EkstreHub icin Net Farklilastiricilar

1. Mail-first ingestion (kullanici mailbox modeli)
2. PDF/CSV parser + confidence + review queue
3. Aidat/ek ucret tespit odagi
4. Coklu mail account + coklu kart + tek panel
5. Self-hosted AI/OCR mimarisi
6. Home Assistant icinde mobil uyumlu calisma

## Product Strategy Implication

- Kisa vadede "tam kapsamli butce app" olmak yerine:
  - ekstre takip,
  - due-date / aidat riski,
  - parser guvenilirligi
  uzerinde derinlesmek daha dogru.

- Orta vadede:
  - otomatik parser kalibrasyonu (onayli),
  - raporlama derinligi,
  - MQTT/HA entity otomasyonlari
  ile teknik moat olusur.

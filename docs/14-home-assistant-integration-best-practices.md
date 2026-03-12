# Home Assistant Integration Best Practices

## Goal

EkstreHub'in Home Assistant add-on modunda sorunsuz, guvenli ve bakimi kolay calismasi.

## Add-on Manifest Standards (`config.yaml`)

- `ingress: true` kullan, disariya gereksiz port acma.
- `ports: {}` ve `ports_description: {}` ile host port yayinini kapali tut.
- `homeassistant_api: true` ve `hassio_api: true` ile gerekli HA API erisimini ac.
- `init: false` ile gereksiz init process overhead'inden kac.
- `arch` listesi yalnizca test edilen mimarileri icersin.
- `url`, `version`, `description` alanlari her release'de guncel olsun.

## Runtime and Data Practices

- Add-on restart durumlarinda veri kaybi olmamasi icin DB ve state disari volume/DB katmanina yazilmali.
- Hassas bilgiler (`IMAP_PASSWORD`, token vb.) options yerine secret mekanizmasi ile verilmeli.
- Add-on loglarina PII ve tam finansal veri yazilmamali.

## Ingress UX Practices

- Dashboard acildiginda once "health + last sync status" goster.
- Parser approval pending durumlari ingress panelde ayri bir bolumde yer alsin.
- Hata mesajlari teknik detaydan cok aksiyon odakli olmali.
- UI mobile-first olmalidir (telefon ekraninda tek sutun, kart tabanli bilgi mimarisi).
- Static asset path'leri relative olmali (Ingress path degisimlerinden etkilenmemek icin).

## Operational Practices

- Her release icin:
  - manifest kontrolu
  - ingress acilis smoke testi
  - API health smoke testi
- HA ve standalone modlarinin davranisi dokumanda birebir eslenmeli.

## Phase Plan Mapping

- Phase 0: manifest standardizasyonu + smoke checklist
- Phase 1: ingress dashboard temel akisi
- Phase 2: parser approval ekrani ve audit izleri
- Phase 3: entity publish iyilestirmeleri ve MQTT backlog hazirligi

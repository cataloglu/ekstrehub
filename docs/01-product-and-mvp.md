# Product and MVP

## Problem

Birden fazla kredi karti kullanan kullanicilar:

- ekstreleri duzenli takip etmez,
- son odeme tarihlerini kacirabilir,
- aidat ve benzeri ek ucretleri gec fark eder,
- toplam kart borcunu tek bir yerde goremez.

Bu durum gereksiz maliyet, gecikme riski ve finansal kontrol kaybina yol acar.

## Product Goal

EkstreHub, kullanicinin tum kredi karti ekstrelerini tek yerde toplayan ve aylik finansal gorunurluk saglayan bir takip sistemidir.

## Core Value Proposition

- Mail kutusuna dusen ekstreleri otomatik toplar
- Her kart icin borc, min odeme ve son odeme bilgisini cikarir
- Aidat / ek ucret kalemlerini isaretler
- Yaklasan son odemeler icin uyarir

## MVP Scope

MVP'de dahil:

- Tek kullanici
- Tek mail kutusu (Gmail/Outlook IMAP)
- PDF/JPG/PNG ekstrelerden veri cikarimi
- Kart bazli aylik ekstre kaydi
- Aidat ve benzeri ek ucret tespiti
- Dashboard + aylik rapor
- Parser farkinda kullanici onay akisi

MVP'de dahil degil:

- Dogrudan banka API entegrasyonu
- Tam otonom parser self-update
- MQTT entegrasyonu
- Coklu kullanici / tenant yapisi

## Success Metrics (MVP)

- Ekstrelerden temel alan cikarim basarisi: >= %90
- Aidat kalemi tespit precision: >= %90
- Son odeme uyari zamaninda uretilme orani: >= %99
- Elle duzeltme gerektiren parse sayisinda aylik dusus

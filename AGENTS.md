# EkstreHub Agent Playbook

Bu dosya, projede calisan AI ajanlarinin ayni standartla ilerlemesi icin operasyonel rehberdir.

## Mission

EkstreHub icin guvenli, izlenebilir ve bakimi kolay bir kod tabani gelistirmek. Finansal veri yanlisligini minimuma indirmek.

## Product Boundaries

- Sistem online calisir.
- Kaynak kanal: kullanicinin kendi mail kutusu (Gmail/Outlook IMAP).
- Banka API entegrasyonu MVP disi.
- Parser degisimi kullanici onayi olmadan active edilmez.
- MQTT entegrasyonu backlog (post-MVP).

## Non-Negotiables

- Tam kart numarasi, CVV, PIN veya sifre saklanmaz.
- Finansal tutarlar `decimal` ile islenir; `float` kullanilmaz.
- Kritik parse alanlari (total debt, due date, minimum payment) validasyonsuz kaydedilmez.
- Drift tespiti olan parser degisimi otomatik yayina alinmaz.
- Tum kritik kararlar audit log'a yazilir.

## Preferred Workflow

1. Ilgili dokumani oku (`docs/*`) ve kapsam dogrula.
2. Kucuk, izole degisiklikler yap.
3. Etkilenen akislari test et.
4. Dokuman ve kodu birlikte guncelle.
5. Commit mesajinda "neden" bilgisini net yaz.

## Service Ownership Map

- Mail alma ve attachment isleme: `mail-ingestor`
- OCR ve dokuman normalize: `document-processor`, `ocr-service`
- Alan cikarimi: `statement-extractor`
- Parser governance: `approval-service`, `parser-registry`
- Raporlama ve bildirim: `reporting-service`, `notification-service`

## Definition of Done

- Is kurali test ile dogrulandi
- Hata senaryosu ele alindi
- Log ve izlenebilirlik dusunuldu
- Dokuman guncellendi
- Guvenlik ve veri minimizasyonu korundu

## Escalation Rules

Asagidaki durumlarda degisiklik durdurulup insan onayi beklenir:

- Parser active versiyon degisimi
- Veri silme/geri donulemez migration
- Finansal hesap sonucunu etkileyen algoritma degisikligi

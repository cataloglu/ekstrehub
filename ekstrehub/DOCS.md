# EkstreHub

Kredi kartı ekstrelerini Gmail'den otomatik indirir, AI ile parse eder ve Home Assistant içinde güzel bir arayüzde gösterir.

## Özellikler

- **Otomatik mail sync** — Gmail/IMAP üzerinden ekstre maillerini çeker
- **AI ile parse** — OpenAI/ChatGPT API ile banka formatlarını otomatik tanır
- **Çoklu banka** — DenizBank, İş Bankası, Garanti BBVA, Yapı Kredi
- **Kategori analizi** — İşlemleri otomatik kategorize eder
- **Ingress** — Home Assistant panelinden doğrudan erişim

## Kurulum Sonrası

1. **Mail hesabı ekle** — Mail & Sync → Gmail App Password ile bağlan
2. **AI Parser ayarla** — Ayarlar → OpenAI API key gir (opsiyonel)
3. **Sync et** — İlk mailleri indir

Detaylı kurulum: [GitHub README](https://github.com/cataloglu/ekstrehub)

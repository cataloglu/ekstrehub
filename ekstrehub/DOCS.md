# EkstreHub

Kredi kartı ekstrelerini Gmail'den otomatik indirir, AI ile parse eder ve Home Assistant içinde güzel bir arayüzde gösterir.

## Özellikler

- **Otomatik mail sync** — Gmail/IMAP üzerinden ekstre maillerini çeker
- **AI ile parse** — OpenAI/ChatGPT API ile banka formatlarını otomatik tanır
- **Çoklu banka** — DenizBank, İş Bankası, Garanti BBVA, Yapı Kredi
- **Kategori analizi** — İşlemleri otomatik kategorize eder
- **Ingress** — Home Assistant panelinden doğrudan erişim

## Kurulum Sonrası

1. **Mail hesabı ekle** — Mail & Sync sekmesinden:
   - **Gmail App Password** (önerilen): Yapılandır → "Şifre / Uygulama Şifresi" seç, Gmail'de 2 adımlı doğrulama açıp [App Password](https://myaccount.google.com/apppasswords) oluştur
   - **Gmail OAuth**: Add-on yapılandırmasında Client ID ve Secret girin (aşağıya bakın)
2. **AI Parser ayarla** — Ayarlar → OpenAI API key gir (opsiyonel)
3. **Sync et** — İlk mailleri indir

## Gmail OAuth (Google ile Bağlan)

"Google ile Bağlan" butonunu kullanmak için:

1. [Google Cloud Console](https://console.cloud.google.com/) → Proje oluştur
2. **APIs & Services** → **Credentials** → **Create Credentials** → **OAuth client ID**
3. Application type: **Web application**
4. Authorized redirect URIs: `https://EV-HOST/api/oauth/gmail/callback` (EV-HOST = Home Assistant adresiniz)
5. Client ID ve Secret'ı kopyala
6. **Ayarlar** → **Eklentiler** → **EkstreHub** → **Yapılandır** → `gmail_oauth_client_id` ve `gmail_oauth_client_secret` alanlarına yapıştır
7. Add-on'u yeniden başlat

Detaylı kurulum: [GitHub README](https://github.com/cataloglu/ekstrehub)

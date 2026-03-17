# EkstreHub

Kredi kartı ekstrelerini Gmail'den otomatik indirir, AI ile parse eder ve Home Assistant içinde güzel bir arayüzde gösterir.

## Özellikler

- **Otomatik mail sync** — Gmail/IMAP üzerinden ekstre maillerini çeker
- **AI ile parse** — OpenAI/ChatGPT API ile banka formatlarını otomatik tanır
- **Çoklu banka** — DenizBank, İş Bankası, Garanti BBVA, Yapı Kredi
- **Kategori analizi** — İşlemleri otomatik kategorize eder
- **Ingress** — Home Assistant panelinden doğrudan erişim

## Kurulum Sonrası

1. **Mail hesabı ekle / sil** — **Mail & Sync** sekmesinde üstten hesabı seç; ayarların altında **Bu mail hesabını sil** ile silebilirsin (onay sorar). Ekstreler silinmez; sadece o hesap bağlantısı kalkar.
2. **Mail hesabı ekle** — Aynı sekmeden:
   - **Gmail App Password** (önerilen): Yapılandır → "Şifre / Uygulama Şifresi" seç, Gmail'de 2 adımlı doğrulama açıp [App Password](https://myaccount.google.com/apppasswords) oluştur
   - **Gmail OAuth**: Add-on yapılandırmasında Client ID ve Secret girin (aşağıya bakın)
3. **AI Parser ayarla** — Ayarlar → OpenAI API key gir (opsiyonel)
4. **Sync et** — İlk mailleri indir

## Gmail OAuth (Google ile Bağlan)

"Google ile Bağlan" butonunu kullanmak için iki yol var:

### A) Add-on yöneticisi tek OAuth client kullanıyorsa (kullanıcı hiçbir şey girmesin)

Add-on yapılandırmasında yönetici bir kez şunları ayarlar; kullanıcılar sadece "Google ile Bağlan"a tıklar:

1. **Redirect proxy** deploy edilir (tek bir sabit redirect URI için). Örnek: `scripts/oauth_redirect_proxy.py` ile bir sunucuda `/callback` yayınlanır (örn. `https://oauth.ekstrehub.io/callback`).
2. [Google Cloud Console](https://console.cloud.google.com/) → Tek proje → OAuth client (Web application) oluştur. **Authorized redirect URIs** = proxy URL (örn. `https://oauth.ekstrehub.io/callback`).
3. **Ayarlar** → **Eklentiler** → **EkstreHub** → **Yapılandır**:
   - `oauth_redirect_proxy_url`: proxy URL (örn. `https://oauth.ekstrehub.io/callback`)
   - `gmail_oauth_client_id` ve `gmail_oauth_client_secret`: Google’dan alınan değerler  
   veya yerleşik client için: `ekstrehub_builtin_gmail_client_id` ve `ekstrehub_builtin_gmail_client_secret`
4. Add-on’u yeniden başlat. Kullanıcılar Client ID/Secret girmeden "Google ile Bağlan" kullanır.

### B) Her kullanıcı kendi Google projesini kullanıyorsa

1. [Google Cloud Console](https://console.cloud.google.com/) → Proje oluştur → OAuth client ID (Web application).
2. **Authorized redirect URIs**: Add-on’da `https://HA-ADRESINIZ/.../api/oauth/gmail/redirect-uri` sayfasına gidip dönen `redirect_uri` değerini Google’a ekleyin.
3. **Ayarlar** → **Eklentiler** → **EkstreHub** → **Yapılandır** → `gmail_oauth_client_id` ve `gmail_oauth_client_secret` alanlarına yapıştır.
4. Add-on’u yeniden başlat.

Detaylı kurulum: [GitHub README](https://github.com/cataloglu/ekstrehub)

## Güncelleme gelmiyorsa

1. **Kod GitHub’a push edilmiş olmalı** — `master` branch’e push edildiğinde CI image’ı (1.0.10 vb.) build eder. Henüz push etmediysen: `git push origin master`.
2. **Home Assistant’ta repo listesini yenile** — **Ayarlar** → **Eklentiler** → sağ üst **⋮** → **Depo’ları yenile** (veya **Repositories** → EkstreHub repo’sunun yanında yenile).
3. **Supervisor’ı yenile** — Bazen **Ayarlar** → **Sistem** → **Yeniden başlat** → sadece **Supervisor’ı yenile** yeterli olur.
4. **Eklenti mağazasında kontrol et** — EkstreHub’a tıkla; “Güncelle” butonu sadece sürüm numarası (config.yaml’daki `version`) yükseltilip image build edildiyse çıkar.

## Güncelleme / kurulum hatası (An unknown error occurred)

1. **Gerçek hatayı gör** — SSH veya Terminal & SSH eklentisiyle: `ha supervisor logs`. En altta addon/ekstrehub ile ilgili satırlara bak (ör. image pull failed, permission denied).
2. **Image çekilemiyorsa (401/403 / pull access denied)** — GitHub'daki container image varsayılan olarak **private** olabilir; HA giriş yapmadan çekemez. **Çözüm:** GitHub → Repo cataloglu/ekstrehub → sağda **Packages** (veya github.com/orgs/cataloglu/packages/container/package/ekstrehub) → pakete gir → **Package settings** → **Danger zone** → **Change visibility** → **Public**. Paket public olunca güncelleme kurulur.
3. **Build yoksa** — GitHub → **Actions** → "Build & Publish Add-on" workflow'unu aç; ilgili commit için build yeşil mi kontrol et. Kırmızıysa hata mesajına göre düzelt.

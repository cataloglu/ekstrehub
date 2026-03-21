# Neden Mac Mail “tek tık”, EkstreHub’da OAuth kurulumu var?

## Kısa cevap

**Mail (macOS)** ve **iPhone Posta** uygulaması, Google ile **yıllardır anlaşmalı** bir istemci kimliği kullanır; Google bu uygulamalara “güvenilir istemci” gibi davranır. Sen “Hesap ekle → Google” dersin, **Apple’ın** Google’a kayıtlı OAuth uygulaması devreye girer — senin Google Cloud’da proje açman gerekmez.

**EkstreHub** (veya Thunderbird, Outlook masaüstü, kendi sunucunuzdaki web uygulaması) **üçüncü parti** bir yazılımdır. Google’ın kurallarına göre:

- Posta/IMAP için OAuth kullanacaksan **sen (veya add-on yöneticisi)** [Google Cloud Console](https://console.cloud.google.com/)’da bir **OAuth 2.0 istemcisi** oluşturmalısın.
- **Yönlendirme URI’si** (redirect URI) Google’da **birebir** tanımlı olmalı.
- Uygulama “Testing” modundaysa **test kullanıcıları** listesine e-postanı eklemelisin.

Bu Google’ın [OAuth 2.0 web sunucu akışı](https://developers.google.com/identity/protocols/oauth2/web-server) ile uyumludur; “basit” görünen Mail akışı ile aynı **protokol**, farklı olan **kimlik bilgisinin kime ait olduğu**.

---

## Google’ın resmi dokümantasyonu (okuman gerekenler)

| Konu | Resmi link |
|------|------------|
| OAuth 2.0 genel | https://developers.google.com/identity/protocols/oauth2 |
| **Web sunucu uygulaması** (bizim akış) | https://developers.google.com/identity/protocols/oauth2/web-server |
| Gmail / **IMAP ve XOAUTH2** | https://developers.google.com/workspace/gmail/imap/xoauth2-protocol |
| IMAP, POP, SMTP (Gmail) | https://developers.google.com/gmail/imap/imap-smtp |
| Gmail API – sunucu tarafı yetkilendirme | https://developers.google.com/workspace/gmail/api/auth/web-server |

EkstreHub sunucuda **yetkilendirme kodunu** değiştirip refresh token saklar; IMAP’te [XOAUTH2](https://developers.google.com/workspace/gmail/imap/xoauth2-protocol) kullanır — Google’ın önerdiği model budur.

---

## Google’ın örnek / araç reposu (GitHub)

- **gmail-oauth2-tools** (Google): https://github.com/google/gmail-oauth2-tools  
  Komut satırından OAuth test ve IMAP XOAUTH2 denemeleri için.

Bu repo, Google’ın dokümantasyonunda da referans verilen resmi örneklerden biridir.

---

## EkstreHub’da ne yapmalısın? (özet)

1. **Home Assistant → Eklentiler → EkstreHub → Yapılandırma**  
   - `gmail_oauth_client_id`  
   - `gmail_oauth_client_secret`  
   (Google Cloud → APIs & Services → Credentials → OAuth 2.0 Client ID → Web application)

2. **Authorized redirect URIs** (Google tarafında):  
   EkstreHub’un döndürdüğü adres ile **aynı** olmalı. Add-on çalışırken:  
   `GET /api/oauth/gmail/redirect-uri` (Ingress altında tam URL) — dönen `redirect_uri` değerini Google’a ekle.

3. **OAuth consent screen**  
   - Uygulama “Testing” ise: **Test users** listesine Gmail adresini ekle.  
   - Aksi halde “Error 403: access_denied” veya sadece test hesapları çalışır.

4. **Gmail API** (isteğe bağlı ama önerilir): API Library’den Gmail API’yi etkinleştir.

5. Add-on’u **yeniden başlat**, ardından arayüzde **Gmail’e bağlan** (OAuth add-on’da tanımlıysa).

---

## Şifre ile “normal” Gmail girişi

Google, IMAP için **hesap şifresini** çoğu senaryoda kabul etmez; **Uygulama şifresi** (16 karakter) veya OAuth gerekir. Bu da Google’ın güvenlik politikasıdır; EkstreHub’a özel değildir.

---

## Özet tablo

| | Mac/iOS Mail | EkstreHub |
|---|--------------|-----------|
| OAuth istemcisi | Apple’ın Google’daki kaydı | Senin / yöneticinin Google Cloud projesi |
| Redirect URI | Sen yönetmezsin | `redirect-uri` endpoint ile birebir eşleşmeli |
| Kullanıcı işi | Hesap ekle | Add-on config + (gerekirse) test user |

Bu yüzden “Mail kadar basit” değil — **aynı güvenlik modeli**, farklı **istemci sahibi**.

# EkstreHub Changelog

## 1.0.29 (2026-02-21)

### Dokümantasyon
- **Gmail OAuth (Google resmi)**: Mac Mail ile karşılaştırma, Google doküman linkleri, `gmail-oauth2-tools` — `docs/30-google-oauth-mac-mail-vs-ekstrehub.md` + add-on `DOCS.md` güncellendi.

---

## 1.0.28 (2026-02-21)

### Düzeltmeler
- **Gmail OAuth yokken** «Gmail’e bağlan» artık `/api/oauth/gmail/start` adresine **gitmiyor** (HA’ya `?oauth=not_configured` ile dönme yok). Üstte uyarı + buton yalnızca mesaj gösterir; OAuth add-on’da tanımlıysa Google’a açılır.

---

## 1.0.27 (2026-02-21)

### İyileştirmeler
- Gmail OAuth: Google URL’sine `prompt=select_account consent` (hesap seç + izin; diğer uygulamalardaki gibi).
- Mail & Sync: «Gmail’e bağlan»ın **Google’ın sitesinde** hesap seçme ekranı açtığı ve OAuth için add-on’da Client ID/Secret gerektiği metinde açıklandı.

---

## 1.0.26 (2026-02-21)

### Düzeltmeler
- **Gmail OAuth yeni sekme**: `window.open(..., "noopener")` tarayıcıda `null` döndüğü için kod yanlışlıkla iframe’i `location.assign` ile değiştiriyordu; Google girişi açılmıyordu. `noopener` kaldırıldı, `w.opener = null` ile güvenlik korunuyor; gerekirse `window.top.open` deneniyor.

---

## 1.0.25 (2026-02-21)

### İyileştirmeler
- **Gmail IMAP `AUTHENTICATIONFAILED`**: API artık Türkçe açıklama döner (normal şifre yerine uygulama şifresi / OAuth). Arayüzde Gmail manuel kurulum metni netleştirildi.

---

## 1.0.24 (2026-02-21)

### Düzeltmeler
- **OAuth yapılandırılmadı yönlendirmesi**: `?oauth=not_configured` öncesi path’te sondaki `/` eksikti (`.../TOKEN?oauth=...`). Home Assistant Ingress bu URL’de **404** veriyor; artık `.../TOKEN/?oauth=...`.

---

## 1.0.23 (2026-02-21)

### Düzeltmeler
- **Gmail OAuth (Ingress)**: “Gmail’e bağlan” tıklanınca link bazen açılmıyordu (iframe / sandbox). `window.open` + yeni sekme engellenirse aynı sekmede `location.assign` ile açılır.

---

## 1.0.22 (2026-02-21)

### Düzeltmeler
- **Ingress 404 (kalıcı)**: `index.html` içindeki `./assets/...` yolları sunucuda **`/api/hassio_ingress/{token}/assets/...`** olarak yeniden yazılıyor — `<base>` çözümlemesine tek başına güvenilmiyor. `X-Ingress-Path` yoksa **Referer** içinden `hassio_ingress` veya `/app/<slug>` çıkarımı.

---

## 1.0.21 (2026-02-21)

### Düzeltmeler
- **Ingress 404 (resmi HA davranışı)**: Home Assistant Core `X-Ingress-Path` değerini `/api/hassio_ingress/{token}` olarak set eder; adres çubuğundaki `/app/<slug>` ile aynı değildir. `<base href>` tekrar bu header’dan üretiliyor (1.0.20’deki `location.pathname` önceliği kaldırıldı).

---

## 1.0.20 (2026-02-21)

### Düzeltmeler
- **HA Ingress / siyah 404 (kök neden)**: Add-on konteynerine çoğu zaman `GET /` gelir; `X-Ingress-Path` eksik veya proxy’de kaybolabiliyor. `<base href>` artık **tarayıcıdaki** `location.pathname` ile (inline script + Vite `transformIndexHtml`) ayarlanıyor — toplulukta Frigate vb. için önerilen yöntem.

---

## 1.0.19 (2026-02-21)

### Düzeltmeler
- **HA Ingress / siyah ekran 404**: `.../app/<slug>` adresi sonunda `/` olmadan açılınca `./assets/` yanlışlıkla `/app/assets/...` oluyordu. `index.html` yanıtında **her zaman** `<base href>` enjekte edilir (`X-Ingress-Path` veya `/app/<slug>/` çıkarımı; eski `/hassio/ingress/...` için de).
- **Gmail OAuth linki**: `apiUrlPath()` artık `fetch("api/...")` ile aynı şekilde `<base href>` kullanıyor.

---

## 1.0.17 (2026-03-17)

### Düzeltmeler
- **HA Ingress / Gmail OAuth**: “Gmail’e bağlan” linki artık `window.location.pathname` ile tam URL üretiyor; `<base href>` yüzünden yanlış path’e gidip **404** olma sorunu giderildi.

---

## 1.0.16 (2026-03-17)

### UX
- **Gmail**: Varsayılan akış Mail / Outlook gibi — **Gmail’e bağlan (tarayıcıda aç)** ile Google oturum sayfası; uygulama şifresi gizli “OAuth çalışmıyorsa…” altında.
- OAuth ayarsız geri dönüşte manuel IMAP bölümü otomatik açılır.

---

## 1.0.15 (2026-03-17)

### Kritik düzeltme
- **Gmail + App Password**: Gmail seçiliyken form yanlışlıkla OAuth (textarea) gösteriyordu; API şifreyi `imap_password` alanından bekliyordu. Kullanıcı uygulama şifresini textarea’ya yazınca 422 oluşuyordu. Artık şifre modunda doğru alan (tek satır şifre) gösteriliyor.

---

## 1.0.14 (2026-03-17)

### Düzeltmeler
- **422 hatası**: Hesap eklerken doğrulama hatası (eksik alan) artık anlamlı gösteriliyor (örn. "E-posta adresi: Field required")
- **Hesap Ekle** butonu: E-posta veya şifre boşken devre dışı (Gmail App Password ile)

---

## 1.0.13 (2026-03-17)

### Yenilikler
- **Mail hesabı silme**: Mail & Sync → hesabı seç → altta **Bu mail hesabını sil** (onay penceresi)

---

## 1.0.12 (2026-03-17)

### Düzeltmeler
- Gmail + OAuth yokken sadece "Şifre / Uygulama Şifresi" gösteriliyor; OAuth hesabı yanlışlıkla oluşturulmuyor
- Hesap eklerken (Gmail, OAuth yok) her zaman password modu kullanılıyor

---

## 1.0.11 (2026-02-21)

### Düzeltmeler
- **Gmail OAuth refresh hatası**: Token süresi dolunca net mesaj + "Hesabı silip yeniden ekleyin" (App Password veya Google ile Bağlan)
- **Hata mesajları**: API `detail` yanıtı artık UI’da gösteriliyor; sync/IMAP hataları sebebiyle birlikte gösteriliyor
- **Gmail App Password**: Şifre/e-posta trim, uygulama şifresindeki boşluklar kaldırılıyor; IMAP’ı açma linki eklendi

---

## 1.0.10 (2026-02-21)

### Yenilikler
- **Gmail OAuth — kullanıcı Client ID/Secret girmek zorunda değil**: Add-on yöneticisi tek OAuth client + redirect proxy ayarlarsa kullanıcılar sadece "Google ile Bağlan"a tıklar
- Yerleşik client desteği: `ekstrehub_builtin_gmail_client_id` / `ekstrehub_builtin_gmail_client_secret` ve `oauth_redirect_proxy_url` ile tek tık OAuth
- OAuth redirect proxy script'i: `scripts/oauth_redirect_proxy.py` (tek sabit redirect URI için)

---

## 1.0.9 (2026-03-21)

### Düzeltmeler
- **Gmail OAuth**: Referer header fallback — proxy header'ları yoksa (HA Ingress) sayfa URL'sinden redirect_uri oluşturuluyor

---

## 1.0.8 (2026-03-21)

### Düzeltmeler
- **Gmail OAuth (HA Ingress)**: redirect_uri artık X-Forwarded-Host, X-Forwarded-Proto ve X-Ingress-Path header'larından doğru oluşturuluyor — localde çalışan OAuth artık HA'da da çalışır
- OAuth callback sonrası yönlendirme ingress path'e göre yapılıyor
- `/api/oauth/gmail/redirect-uri` endpoint'i: Google Cloud Console'a eklenecek URI'yi gösterir

---

## 1.0.7 (2026-03-21)

### Düzeltmeler
- **OAUTH_NOT_CONFIGURED**: Gmail OAuth yapılandırılmamışsa artık net mesaj + App Password alternatifi gösteriliyor
- Gmail için "Şifre / Uygulama Şifresi" (App Password) seçeneği eklendi — OAuth olmadan da Gmail bağlanabilir
- Health API: `gmail_oauth_configured` alanı eklendi
- DOCS.md: Gmail OAuth kurulum rehberi eklendi

---

## 1.0.6 (2026-03-21)

### Düzeltmeler
- **404 hatası (HA Ingress)**: `X-Ingress-Path` header kullanılarak index.html'e `<base href>` enjekte ediliyor — tüm API ve asset path'leri artık doğru çözümleniyor
- Frigate, motionEye gibi add-on'lardaki kanıtlanmış yöntem uygulandı

---

## 1.0.5 (2026-03-21)

### Düzeltmeler
- **404 hatası giderildi**: HA Ingress alt path'te (örn. `/app/xxx`) Mail hesabı ekle / Google ile Bağlan tıklandığında 404 dönme sorunu çözüldü
- API çağrıları ve OAuth linki artık mevcut base path'e göre doğru çözümleniyor

---

## 1.0.4 (2026-03-21)

### Düzeltmeler
- Migration 0009: parse_status, parsed_json kolonları eklendi

---

## 1.0.3 (2026-03-21)

### HA Uyumluluk
- /data path fix, config.yaml iyileştirmeleri

---

## 1.0.2 (2026-03-21)

### Düzeltmeler
- SQLite uyumluluğu: `now()` → `CURRENT_TIMESTAMP`, PostgreSQL regex kaldırıldı
- SQLite batch_alter_table: 0005, 0006, 0007, 0008 constraint/index değişiklikleri
- İlk kurulumda syntax error ve OperationalError giderildi

---

## 1.0.1 (2026-03-21)

### Düzeltmeler
- Alembic migration 0008 `down_revision` düzeltildi — ilk kurulumda KeyError giderildi
- Add-on artık düzgün başlıyor

---

## 1.0.0 (2026-03-08)

### İlk Sürüm
- Gmail IMAP üzerinden otomatik ekstre indirme
- AI ile PDF/CSV parse (OpenAI, Ollama, custom LLM)
- Çoklu Gmail hesabı, otomatik sync
- Ekstre listesi, global arama, kategori analizi
- Home Assistant Ingress desteği

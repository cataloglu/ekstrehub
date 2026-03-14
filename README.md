# EkstreHub — Kredi Kartı Ekstre Takip Sistemi

Home Assistant add-on'u. Gmail'den kredi kartı ekstrelerini otomatik indirir,  
AI ile parse eder ve güzel bir arayüzde gösterir.

---

## Kurulum

### 1. Depoya Ekle

Home Assistant → **Ayarlar → Add-ons → Add-on Mağazası → ⋮ → Depolar**

```
https://github.com/cataloglu/ekstrehub
```

### 2. Add-on'u Yükle

**EkstreHub** add-on'unu bulup **Yükle**ye tıkla.

### 3. Yapılandır (isteğe bağlı)

`config.yaml` seçenekleri:

| Seçenek | Açıklama | Varsayılan |
|---|---|---|
| `log_level` | Log seviyesi | `info` |
| `gmail_oauth_client_id` | Gmail OAuth için (isteğe bağlı) | `` |
| `gmail_oauth_client_secret` | Gmail OAuth için (isteğe bağlı) | `` |

### 4. Başlat

Add-on'u başlat → **Aç** butonuna tıkla → EkstreHub açılır.

---

## İlk Kurulum (Add-on Açıldıktan Sonra)

### Mail Hesabı Ekle

1. Sol menü → **Mail & Sync**
2. **+ Hesap Ekle** → Gmail seç
3. Gmail hesabın ve **App Password** gir  
   _(Google → Güvenlik → 2FA aktif → App Passwords → "EkstreHub" için şifre oluştur)_
4. **Kaydet** → **Şimdi Sync Et**

### AI Parser Kur

1. Sol menü → **Ayarlar → AI Parser**
2. Provider: **OpenAI**
3. API Key: OpenAI'dan aldığın `sk-...` key
4. **Bağlantıyı Test Et** → ✅ Bağlantı başarılı
5. **Kaydet**

### Otomatik Sync Aç

1. **Ayarlar → Otomatik Sync**
2. Açık yap, aralık seç (örn: her 60 dakika)

---

## Gmail App Password Nasıl Alınır?

1. [Google Hesabım](https://myaccount.google.com) → **Güvenlik**
2. **2 Adımlı Doğrulama** açık olmalı
3. Arama kutusuna "App passwords" yaz → **Uygulama şifreleri**
4. Uygulama: **Diğer (Özel ad)** → "EkstreHub" yaz → **Oluştur**
5. 16 haneli şifreyi kopyala → EkstreHub'a gir

---

## Veri Güvenliği ve Güncellemeler

- Tüm veriler (veritabanı, ayarlar) `/data/` dizininde saklanır
- Add-on **güncellemeleri veri silmez**
- Veritabanı migrasyonları sadece tablo/sütun ekler, siler
- `/data/ekstrehub.db` → SQLite veritabanı (ekstreler, mail hesapları)
- `/data/app_settings.json` → AI/LLM ayarları
- `/data/auto_sync_settings.json` → Otomatik sync ayarları

---

## Desteklenen Bankalar

- **İş Bankası** (PDF)
- **Garanti BBVA** (PDF)
- **Yapı Kredi** (PDF)
- **DenizBank** (PDF)
- Diğer bankalar: AI otomatik tanımlama ile çalışır

---

## Sorun Giderme

### Mail bağlanamıyor
- App Password doğru mu? (16 karakter, boşluksuz)
- Gmail IMAP açık mı? (Gmail → Ayarlar → Tüm Ayarlar → İletme ve POP/IMAP)
- Sistem Logları sayfasında hata detayına bak

### Ekstre parse edilemiyor
- AI Parser ayarları doğru mu? (Bağlantıyı Test Et)
- Dosya PDF/CSV formatında mı?
- Sistem Logları sayfasında `parse_failed` detayına bak

### Uygulama açılmıyor
- Add-on loglarını kontrol et (HA → Add-ons → EkstreHub → Günlükler)

---

## Lisans

MIT — Özgürce kullan, değiştir, dağıt.

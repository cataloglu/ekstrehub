# EkstreHub Changelog

## 1.0.67 (2026-04-10)

### Düzeltmeler
- **Eski hatırlatmalar için UI fallback ayrıştırma**: Daha önce parse edilmiş ekstrelerde `remaining_value_try` boş olsa bile, arayüz hatırlatma metninden kalan puan/mil tutarını çıkarıp kart/program toplamlarında gösterir.
- **Puan/mil bölümü görünürlüğü**: “Puan / Mil Son Kullanım” bölümü özet ekranında artık her zaman görünür; kayıt yoksa kaybolmak yerine açık bir boş durum mesajı gösterir.

---

## 1.0.66 (2026-04-04)

### Düzeltmeler
- **Banka metin varyasyonlarına uygun puan/mil ayrıştırma**: Bozuk karakterli/encoding bozulmuş satırlarda da (`�`) kalan puan/mil değeri daha güvenilir yakalanır (`remaining_value_try`).

---

## 1.0.65 (2026-04-04)

### İyileştirmeler
- **Özet ekranı ödeme görünürlüğü**: “Yaklaşan Son Ödemeler” bölümü eklendi; kart bazında son ödeme tarihi, toplam/minimum tutar ve aciliyet vurgusu tek bakışta anlaşılır hale getirildi.

---

## 1.0.64 (2026-04-04)

### Özellikler
- **Puan/mil dashboard toplamı**: Mevcut ekstrelerden kalan puan/mil değeri toplanır; kart/program bazında tek ekranda özetlenir.
- **Hatırlatma verisi zenginleştirildi**: Puan/mil hatırlatmalarından `loyalty_program` ve `remaining_value_try` alanları çıkarılır.

---

## 1.0.63 (2026-04-04)

### Özellikler
- **Mevcut yanlış parse kayıtları için tek tık temizlik**: AI Parser bölümüne, kredi kartı dışı şüpheli ekstreleri (max 50) yeniden çözdürüp `non_credit_card_document` olarak temizleyen yeni aksiyon eklendi.

---

## 1.0.62 (2026-04-04)

### Düzeltmeler
- **Kredi kartı olmayan PDF ayıklama**: Parser “İşlem Sonuç Formu”, fon alış/satış gibi yatırım/dekont belgelerini kredi kartı ekstresi olarak parse etmez; bu dosyaları `non_credit_card_document` olarak işaretler.
- **Yeniden çöz hata mesajı netleşti**: Reparse akışı bu durumda özel hata kodu döner, arayüzde anlaşılır açıklama gösterilir.

---

## 1.0.61 (2026-04-04)

### Düzeltmeler
- **Yeniden çöz çift tıklama koruması**: Bir ekstre yeniden çözülürken yeni istek başlatılmaz; çakışan çağrılardan kaynaklanan yanlış UI hata durumu engellendi.

---

## 1.0.60 (2026-04-04)

### Özellikler
- **HA sensöründe ekstre detayları**: Yeni ekstre bildirimlerinde sensör attribute’larına ekstre bazında `due_date` ve `total_debt` bilgileri eklendi (`statement_details`, `latest_due_date`, `latest_total_debt`).

### Düzeltmeler
- **Hatırlatma gürültüsü azaltıldı**: Ekstre hatırlatma çıkarımı genel hesap başlığı bloklarını atlar; kart detayındaki hatırlatma listesi yalnızca sadakat puanı/mil son kullanım kayıtlarını gösterir.

---

## 1.0.59 (2026-04-04)

### Düzeltmeler
- **HA bildirim yetkilendirmesi**: Add-on yapılandırmasına `homeassistant_api` ve `hassio_api` izinleri eklendi; sync sonrası bildirim/sensör yazımında görülen `401 Unauthorized` sorunu giderildi.
- **Teşhis logları iyileştirildi**: `ha_notify_failed` artık HTTP durumunu ve gövde özetini yazar; yetki eksikse doğrudan çözüm ipucu verir.

---

## 1.0.58 (2026-04-04)

### Düzeltmeler
- **Puan/mil son kullanım doğruluğu**: Hatırlatma tarih seçimi artık metin çevresine göre puanlanır; `Hesap Kesim`, `Son Ödeme`, `Dönem Borcu` gibi ekstre başlığı tarihleri son kullanım tarihi sanılmaz.
- **Expiry sınıflandırması sıkılaştırıldı**: Kayıtlar yalnızca açık son kullanım/sona erme ifadesi varsa `expiry` olur; “Puan / Mil” panelindeki yanlış pozitifler azaltıldı.

---

## 1.0.57 (2026-04-03)

### Özellikler
- **Dashboard sadeleştirme**: “Puan / Mil Son Kullanım” paneli artık sadece harcanması gereken puan/mil kayıtlarını gösterir; yasal/servis hatırlatmaları bu bölümden çıkarıldı.

---

## 1.0.56 (2026-03-31)

### Düzeltmeler
- **Parser timeout dayanıklılığı**: LLM timeout aldığında ekstre hemen `parse_failed` olmaz; artırılmış timeout ile bir kez otomatik retry yapılır.
- **İzlenebilirlik**: Retry ile başarılı parse kayıtlarına `llm_retry_success` notu eklenir.

---

## 1.0.55 (2026-03-31)

### Özellikler
- **Home Assistant otomatik bildirim**: Yeni ekstre kaydedildiğinde EkstreHub artık HA'ya `persistent_notification.create` gönderir ve `sensor.ekstrehub_new_statements` ile `sensor.ekstrehub_last_sync` durumlarını günceller (manuel webhook gerekmez).
- **Her iki akışta da çalışır**: Bildirimler hem manuel sync hem auto-sync sonrası tetiklenir.

### Düzeltmeler
- **Legacy DB dayanıklılığı**: `learned_parser_rules` tablosu eksik olsa bile parser akışı kesilmeden devam eder.

---

## 1.0.54 (2026-03-31)

### Düzeltmeler
- **Legacy DB uyumu**: `learned_parser_rules` tablosu olmayan kurulumlarda parser akışı kırılmadan devam eder.
- **Uçtan uca doğrulama**: Tüm posta kutusu yeniden indirme + failed-only yeniden çöz akışı doğrulandı; bekleyen/hatalı dosya kalmadan parse tamamlanır.

---

## 1.0.53 (2026-03-24)

### Düzeltmeler
- **CSV parse hatası sessiz kayıp**: Hatalı CSV artık `parse_failed` satırı olarak kaydedilir (Dosyalar'da görünür).
- **İçerik dedupe yanlış pozitif**: Aynı banka/dönem farklı kart veya farklı toplam borç olan ekstreler artık atlanmaz (`total_due_try` + `card_number` dahil).
- **LLM tx amount crash**: `"1.234,56"` gibi TR formatı veya geçersiz değerler artık sessizce 0 yerine `_parse_float` ile doğru parse edilir; `round(2)` sınırı.
- **LLM truncation**: Uzun PDF'ler sayfa bazlı (form-feed) bölünür; orta sayfa kaybı azaltılır.
- **JSON repair**: Brace-matching tabanlı; sabit whitespace bağımlılığı kaldırıldı.
- **PDF extract**: Encrypted/corrupt/boş PDF'ler `PDFExtractionError` ile net hata; parse_failed olarak kaydedilir.
- **Boş metin LLM'e gönderilmez**: 50 karakterden kısa metin `text_too_short` notu ile short-circuit.
- **is_llm_failure_empty**: `no_transactions_found` olan tüm parse'lar artık `parse_failed` sayılır (0 işlemli ama `parsed` etiketli ekstreler önlenir).
- **Kart numarası tespiti**: Arama penceresi 3000→8000 karakter.
- **Heuristic metadata**: 25K sınırı yerine head+tail tarama; uzun PDF sonundaki bilgiler de bulunur.
- **Parse doğrulama**: `minimum > total`, ters dönem tarihleri, erken due_date uyarı notları.
- **LLM prompt**: Anti-hallucination kuralı eklendi.

---

## 1.0.52 (2026-03-24)

### Düzeltmeler
- **SQLite `database is locked`**: WAL, uzun busy timeout, uygun bağlantı ayarları; mail sync ile toplu yeniden çöz aynı anda DB’ye yazmasın diye **tek sıra kilidi** (sync + batch re-parse birbirini bekler).
- **İş Bankası / Maximiles**: PDF’te logo görsel olduğunda metin ipuçları (`maximiles.com`, `MAXIMIL`, `0850 724` vb.) banka tespitinde öncelikli; `PARAM/GETIR` satırı tek başına Param sayılmaz.

### Özellikler
- **Ekstreler**: Satırda **Banka** açılır listesi — otomatik tespit yanlışsa manuel düzeltme (API `PATCH` ile aynı).

---

## 1.0.51 (2026-02-21)

### Düzeltmeler
- **Ekstrelerde `—` tarih**: Öğrenilmiş kurallar sadece işlem satırı çıkarıyordu; LLM açıkken artık tam parse (dönem/tutar). LLM hata verirse öğrenilmiş işlemler korunur, PDF’den heuristik tarih.

---

## 1.0.50 (2026-02-21)

### Düzeltmeler
- **Yeniden çöz + Param**: Veritabanında `Param` yazıyorsa e-posta / PDF bankası öncelikli; learned-rules Param’a kilitlenmez.
- Reparse hatalarında anlamlı Türkçe mesaj (PDF bulunamadı, mail hesabı yok).

## 1.0.49 (2026-02-21)

### Özellikler
- **Özet**: Puanlar & hatırlatmalar paneli (Pazarama / MaxiMil son tarihleri), KPI rozeti.

## 1.0.48 (2026-02-21)

### Özellikler
- PDF’ten **ekstre hatırlatmaları** (`statement_reminders`): puan son tarihi, uyarılar.

---

## 1.0.47 (2026-03-22)

### Özellikler
- **Dosyalar** sekmesi: Mailden indirilen tüm PDF/CSV ekleri, parse durumu (başarılı / hatalı / bekleyen) ve özet sayaçlar. **Ekstreler** yalnızca başarılı analizi gösterir; eksik veya hatalı satırlar burada.
- Kenar çubuğunda **Dosyalar** üzerinde turuncu rozet: analiz bekleyen veya hatalı dosya sayısı (`non_parsed`).

---

## 1.0.46 (2026-03-22)

### Özellikler
- **Orijinal PDF**: Ekstre satırında **Orijinal PDF** linki — posta kutusundan PDF açılır (doğrulama için). PDF sunucuda saklanmaz; açılışta IMAP’ten çekilir.

### Düzeltmeler
- **Param bankası yanlışlı**: PDF metninde `parametre` gibi kelimeler içindeki `param` geçişi “Param” bankası sanılıyordu; artık sadece kelime olarak `param` eşleşir.

### İyileştirmeler
- AI: `bank_name` alanına ödeme/ cüzdan markası değil, ekstreyi düzenleyen banka yazılması hatırlatması.

---

## 1.0.45 (2026-03-22)

### Özellikler
- **Aynı mailleri tekrar indir**: Ekstreleri sildiyseniz bile sistem aynı maili «zaten işlendi» sayabilir (`duplicate_messages`). **Ayarlar → Sistem → «Posta önbelleğini temizle»** — onay `POSTA`. Sonra **Mail ile senkronize et**. Öğrenilmiş kurallar ve denetim logları silinmez (tam silme için `SIFIRLA`).

---

## 1.0.44 (2026-03-22)

### Düzeltmeler
- **Banka adı «null»**: LLM bazen JSON’da `bank_name` alanına metin `"null"` yazıyordu; Python’da bu değer dolu sayıldığı için e-posta/PDF’den gelen banka ipucu uygulanmıyordu. Tüm ipuçları `bank_identification` modülünde normalize + kanonik isim (İş/Yapı Kredi) ile birleştiriliyor; API’de eski kayıtlar da okunurken düzeltiliyor.
- **Profil isimleri**: Gmail konusu/gönderenden tespit `İş Bankası` / `Yapı Kredi` ile hizalandı; öğrenilmiş kurallar tablosunda eski `Is Bankasi` / `Yapi Kredi` anahtarları hâlâ bulunur.

### Testler
- `tests/test_bank_identification.py` (normalize, LLM null → ipucu, learned keys).

---

## 1.0.43 (2026-03-21)

### Düzeltmeler
- **Aktivite logu / TSV**: `parse_failed` ekstrelerde de `parse_notes` ve banka adı `parsed_json`’dan okunur (önceden sadece başarılı parse’ta dolduruluyordu; dışa aktarımda `notlar=` boş görünüyordu).

---

## 1.0.42 (2026-03-21)

### İyileştirmeler
- **Loglar** sekmesi: varsayılan **tablo** görünümü, **düz metin** ve **kart** seçenekleri; **Panoya kopyala** / **.txt indir** (TSV, Excel uyumlu). Kopyalama HA/Ingress için güçlendirildi.
- **Ayarlar → Sistem Logları**: tablo + TSV kopyala / indir.

---

## 1.0.41 (2026-03-21)

### İyileştirmeler
- **Parser teşhis logları**: `text_fp` (metin özeti), `parser_parse_start` / `parser_parse_done` (path: learned_local / llm / llm_failed / no_llm), öğrenilmiş kurallarda `learned_skip` nedeni; LLM’de `llm_call_start`, sıfır işlem uyarısı.

---

## 1.0.40 (2026-03-21)

### Özellikler
- **Ayarlar → Sistem → Test**: Tüm **öğrenilmiş parser kurallarını** sil (onay: `KURALLAR`). Ekstreler silinmez; sonra «Yeniden çöz» veya toplu reparse ile LLM’den yeniden üretilir.

---

## 1.0.39 (2026-03-21)

### Düzeltmeler
- **LLM zaman aşımı**: Varsayılan istek süresi **180 sn** (60 sn sık yetmiyordu). `llm_timeout` / `llm_failed` notları ayrıldı; zaman aşımında ekstre **`parse_failed`** ve reparse **başarısız** sayılır (önceden yanlışlıkla başarılı görünüyordu).
- **Öğrenilmiş regex**: En az **1** satır eşleşmesi yeterli (önceki `need>=3` DenizBank gibi durumlarda `learn_rules_too_few_matches` engelliyordu).

---

## 1.0.38 (2026-03-21)

### Özellikler
- **Ayarlar → Sistem**: Onaylı veri sıfırlama — tüm ekstre/mail ingestion kayıtları, öğrenilmiş parser ve denetim logları silinir; mail hesapları ve AI ayarları kalır. Onay için `SIFIRLA` yazılır.

---

## 1.0.37 (2026-03-21)

### Özellikler
- **Ekstreler** sekmesinde her PDF için **«Yeniden çöz»** (↻); seçili ekstreler için toplu **«Seçilenleri yeniden çöz»** — Ayarlar’a gitmeden mailden PDF tekrar alınır ve LLM ile parse edilir.

---

## 1.0.36 (2026-03-21)

### Özellikler
- **Öğrenilmiş yerel parser**: LLM bir ekstreyi başarıyla çözdükten sonra aynı banka için regex JSON üretilir (`learned_parser_rules` tablosu). Sonraki PDF’lerde önce bu kurallar denenir — **API çağrısı yok**; eşleşmezse yine LLM’e düşülür. Eğitimi kapatmak: `EKSTREHUB_DISABLE_LEARN_RULES=1`.

---

## 1.0.35 (2026-03-21)

### Düzeltmeler
- **AI yeniden parse**: Tek istek çok uzun sürdüğünde HA/proxy tarayıcıda `TypeError: Load failed` verebiliyordu; arayüz artık ekstreleri **tek tek** `POST` ile işler.
- OpenAI varsayılan LLM **zaman aşımı 180 sn** (büyük PDF’lerde 60 sn yetmiyordu).

---

## 1.0.34 (2026-03-21)

### Özellikler
- **AI Parser**: LLM sonradan açıldığında eski PDF ekstreleri yeniden çözmek için `POST /api/statements/reparse` ve arayüzde **Boş/hatalı ekstreleri yeniden çöz** / **Tüm PDF’leri yeniden çöz** (IMAP’ten PDF tekrar alınır, güncel LLM ayarları kullanılır).

---

## 1.0.33 (2026-03-21)

### İyileştirmeler
- Mail & Sync: **Sadece okunmamış (UNSEEN)** için açık/kapa (Gmail’de ekstreyi okuduysan tarama 0 kalıyordu — kapatınca son N mail taranır).
- Maksimum mail sayısı için 20/50/100/200 seçimi.
- `docs/26-mail-account-troubleshooting.md`: «Taranan: 0» senaryosu.

---

## 1.0.32 (2026-03-21)

### Düzeltmeler
- **Otomatik mail sync**: Arka planda `MailIngestionService` eski imza ile oluşturulduğu için (`… takes 1 to 2 positional arguments but 3 were given`) sync tetiklenemiyordu; artık `mail_account` ile oluşturuluyor ve `run_sync()` çağrılıyor (manuel sync ile aynı yol).

---

## 1.0.31 (2026-02-21)

### İyileştirmeler
- **Loglar** sekmesi: aktivite API’si hata verince artık uyarı gösterilir (sessiz başarısızlık yok).
- Kayıt yokken kısa kullanım notu (Senkronize Et, Taranan/Kaydedilen anlamı).
- **Mail Sync** satırında hesap **#id**, **etiket**, **e-posta** ve varsa sunucu **notu** (`/api/activity-log`).

---

## 1.0.30 (2026-02-21)

### İyileştirmeler
- Mail & Sync: Mac Mail’in anahtar sormama nedeni + EkstreHub’da bir kez yönetici ayarı / uygulama şifresi alternatifi (UI metni).

---

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

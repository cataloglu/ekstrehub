# Home Assistant Ingress — resmi URL modeli

Kaynak: Home Assistant Core — `homeassistant/components/hassio/ingress.py`

Ingress isteği add-on konteynerine giderken Core şu header’ı ekler:

```text
X-Ingress-Path: /api/hassio_ingress/{token}
```

(`homeassistant/components/hassio/const.py` içinde `X_INGRESS_PATH = "X-Ingress-Path"`.)

Tarayıcı adres çubuğunda **/app/&lt;slug&gt;** görünse bile, göreli asset ve API yolları için **doğru önek** bu header’daki **`/api/hassio_ingress/{token}/`** tabanıdır. Sadece `location.pathname` (ör. `/app/...`) kullanmak, istekleri yanlış path’e yönlendirir ve 404 üretir.

EkstreHub `index.html` yanıtında `<base href>` değerini **öncelikle** bu header’dan üretir.

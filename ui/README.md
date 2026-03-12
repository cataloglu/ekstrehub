# EkstreHub UI

Bu klasor frontend uygulamasi icin ayrilmistir.

UI, Home Assistant Ingress icinde calisacak sekilde mobile-first olarak tasarlanir.

## Baslatma

- `npm install`
- `npm run dev`

## Build

- `npm run build`

## Test

- `npm test`

## Ingress Notu

- Vite base yolu relative (`./`) tutulur.
- API cagrilari ayni origin uzerinden relative path (`/api/...`) ile yapilir.

## Auth Notu

- Protected endpointler icin `Authorization: Bearer <token>` gerekir.
- UI tokeni once `localStorage["ekstrehub_auth_token"]` anahtarindan okur.
- Eger local storage bossa `VITE_API_AUTH_TOKEN` degeri kullanilir.


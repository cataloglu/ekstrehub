# Auth and Access Decision (MVP)

## Decision Summary

- Auth modeli: single-user bearer token
- Token kaynagi: `API_AUTH_TOKEN` environment variable
- Public endpoint: `GET /api/health`
- Protected endpointler: `Authorization: Bearer <token>` zorunlu

## Protected Scope (Current)

- `GET /api/auth/session`
- `GET /api/cards`
- `GET /api/parser/changes`
- `POST /api/parser/changes/{changeId}/approve`
- `POST /api/parser/changes/{changeId}/reject`

## Security Notes

- Token source code icine hardcode edilmez.
- `API_AUTH_TOKEN` bos ise servis startup'ta fail olur.
- Hata cevaplari standart `error.code` ve `error.message` sekliyle doner.

## Home Assistant Note

Ingress icinde calisan UI, tokeni local storage veya build-time env uzerinden gonderebilir. Bir sonraki adimda Home Assistant oturum bilgisinden guvenli token bootstrap akisi eklenecektir.

# Security and Compliance Baseline

## Data Minimization

- Sadece gerekli finansal alanlar tutulur.
- Tam kart numarasi yerine sadece `last4`.
- CVV, PIN, sifre ve internet bankaciligi bilgileri asla alinmaz/saklanmaz.

## Secrets Management

- IMAP credential bilgileri plaintext tutulmaz.
- Environment secret store veya sifreli credential vault kullanilir.
- Secret rotation kapasitesi hedeflenir.

## Transport and Storage

- Tum dis baglantilar TLS uzerinden yapilir.
- Finansal veri depolama tarafinda encryption-at-rest tavsiye edilir.
- Ham dokuman saklanacaksa storage key + erisim politikasi uygulanir.

## Access Control

- MVP tek kullanici olsa bile endpoint korumasi zorunludur.
- Parser approval aksiyonlari yetki kontrolu gerektirir.
- Audit log degistirilemez formatta tutulmalidir.

## Logging Policy

- Loglara PII ve hassas finansal veri yazilmaz.
- Hata loglarinda maskeli alanlar kullanilir.
- Parser degisiklik ve onay kararlarinin izi tutulur.

## Compliance Notes

- Bolgesel KVKK/GDPR benzeri gereksinimler icin veri silme/export akislari sonraki fazda planlanir.
- "Finansal danismanlik degildir" beyan metni urun icinde gorunur olmalidir.

# DB Migrations and Policy

## Decision

- Veritabani: PostgreSQL
- Migration araci: Alembic

## Initial Scope (Foundation)

Ilk migration su tablolari olusturur:

- `users`
- `cards`
- `statements`
- `parser_versions`
- `parser_change_requests`

## Local Run Steps

1. `.env.example` dosyasini `.env` olarak kopyalayin.
2. DB'yi baslatin:
   - `docker compose --profile db up -d`
3. Python bagimliliklarini kurun:
   - `pip install -r requirements.txt`
4. Migration calistirin:
   - `alembic upgrade head`
5. Son migration'i geri alin (gerektiginde):
   - `alembic downgrade -1`

## Team Policy

- Destructive migration (drop/rename) gerekiyorsa iki asamali gecis tercih edilir.
- Production tarafinda rollback yerine forward-fix ana yaklasimdir.
- Her migration dosyasi net `upgrade()` ve `downgrade()` adimlari icermelidir.
- Finansal tutarliligi etkileyen kolon degisiklikleri release notuna yazilir.

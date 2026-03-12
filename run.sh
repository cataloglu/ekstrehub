#!/usr/bin/with-contenv bashio
# ════════════════════════════════════════════════════════════
#  EkstreHub – Home Assistant add-on startup script
#  /data is persistent storage — survives add-on updates
# ════════════════════════════════════════════════════════════

bashio::log.info "EkstreHub başlatılıyor..."

# ── Environment ──────────────────────────────────────────────
export APP_ENV="production"
export API_HOST="0.0.0.0"
export API_PORT="8000"

# Read log level from add-on options (defaults to info)
export LOG_LEVEL=$(bashio::config 'log_level' 'info')

# ── Database – persistent SQLite in /data ────────────────────
# /data survives add-on updates; database is NEVER wiped on update.
export DB_URL="sqlite:////data/ekstrehub.db"

# ── Gmail OAuth (optional) ────────────────────────────────────
if bashio::config.has_value 'gmail_oauth_client_id'; then
    export GMAIL_OAUTH_CLIENT_ID="$(bashio::config 'gmail_oauth_client_id')"
fi
if bashio::config.has_value 'gmail_oauth_client_secret'; then
    export GMAIL_OAUTH_CLIENT_SECRET="$(bashio::config 'gmail_oauth_client_secret')"
fi

# ── Mail accounts ─────────────────────────────────────────────
# Mail accounts are added through the EkstreHub UI (Settings → Mail & Sync).
# No IMAP credentials needed in config.yaml.
export MAIL_INGESTION_ENABLED="true"

# ── Database migrations ───────────────────────────────────────
# Alembic runs additive-only migrations (no data loss).
# Safe to run on every startup — idempotent.
bashio::log.info "Veritabanı migrasyonları çalıştırılıyor..."
cd /app
python3 -c "
import os, sys
os.environ.setdefault('DB_URL', 'sqlite:////data/ekstrehub.db')
from alembic.config import Config
from alembic import command
cfg = Config('alembic.ini')
cfg.set_main_option('sqlalchemy.url', os.environ['DB_URL'])
command.upgrade(cfg, 'head')
print('Migrations tamamlandı.')
"

if [ $? -ne 0 ]; then
    bashio::log.error "Migration başarısız! Uygulama durduruldu."
    exit 1
fi

# ── Start the application ─────────────────────────────────────
bashio::log.info "API sunucusu başlatılıyor (port 8000)..."
exec python3 -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --no-access-log \
    --log-level "${LOG_LEVEL}"

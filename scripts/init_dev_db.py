"""Initialize all tables needed for local SQLite dev database.

Creates tables that are compatible with SQLite (skips PG-specific regex constraints).
"""
import sqlite3

DB_PATH = "dev-local.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS mail_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL DEFAULT 'custom',
    auth_mode TEXT NOT NULL DEFAULT 'password',
    account_label TEXT NOT NULL,
    imap_host TEXT NOT NULL,
    imap_port INTEGER NOT NULL DEFAULT 993,
    imap_user TEXT NOT NULL,
    imap_password TEXT NOT NULL,
    oauth_refresh_token TEXT,
    mailbox TEXT NOT NULL DEFAULT 'INBOX',
    unseen_only INTEGER NOT NULL DEFAULT 1,
    fetch_limit INTEGER NOT NULL DEFAULT 20,
    retry_count INTEGER NOT NULL DEFAULT 3,
    retry_backoff_seconds REAL NOT NULL DEFAULT 1.5,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS mail_ingestion_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mail_account_id INTEGER REFERENCES mail_accounts(id) ON DELETE SET NULL,
    idempotency_key TEXT UNIQUE,
    status TEXT NOT NULL DEFAULT 'running',
    scanned_messages INTEGER NOT NULL DEFAULT 0,
    processed_messages INTEGER NOT NULL DEFAULT 0,
    duplicate_messages INTEGER NOT NULL DEFAULT 0,
    saved_documents INTEGER NOT NULL DEFAULT 0,
    duplicate_documents INTEGER NOT NULL DEFAULT 0,
    skipped_attachments INTEGER NOT NULL DEFAULT 0,
    failed_messages INTEGER NOT NULL DEFAULT 0,
    csv_rows_parsed INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_type TEXT NOT NULL,
    actor_id TEXT,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    metadata_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS parser_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_name TEXT NOT NULL,
    parser_key TEXT NOT NULL,
    version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'candidate',
    created_by TEXT NOT NULL DEFAULT 'system',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS parser_change_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_name TEXT NOT NULL,
    current_parser_version_id INTEGER REFERENCES parser_versions(id) ON DELETE SET NULL,
    candidate_parser_version_id INTEGER NOT NULL REFERENCES parser_versions(id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    validation_score REAL,
    approval_status TEXT NOT NULL DEFAULT 'pending',
    approved_by TEXT,
    approved_at TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_name TEXT NOT NULL,
    card_alias TEXT NOT NULL,
    card_last4 TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS statements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    parser_version_id INTEGER REFERENCES parser_versions(id) ON DELETE SET NULL,
    period_start TEXT,
    period_end TEXT,
    due_date TEXT,
    total_debt REAL NOT NULL,
    minimum_payment REAL,
    currency TEXT NOT NULL DEFAULT 'TRY',
    parse_confidence REAL,
    status TEXT NOT NULL DEFAULT 'accepted',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS emails_ingested (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mail_account_id INTEGER REFERENCES mail_accounts(id) ON DELETE SET NULL,
    message_id TEXT UNIQUE NOT NULL,
    sender TEXT,
    bank_name TEXT,
    subject TEXT,
    received_at TEXT,
    status TEXT NOT NULL DEFAULT 'processed',
    raw_storage_key TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS statement_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_ingested_id INTEGER NOT NULL REFERENCES emails_ingested(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    mime_type TEXT,
    storage_key TEXT,
    doc_hash TEXT UNIQUE NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    doc_type TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

conn = sqlite3.connect(DB_PATH)
conn.executescript(SCHEMA)
conn.commit()

tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print("Dev DB ready. Tables:")
for t in tables:
    print(f"  - {t[0]}")

conn.close()

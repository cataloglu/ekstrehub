"""Deduplication testi: aynı mail sync iki kez çalıştırılırsa ne olur?"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("DATABASE_URL", "sqlite:///dev-local.db")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("IMAP_HOST", "imap.gmail.com")
os.environ.setdefault("IMAP_PORT", "993")
os.environ.setdefault("IMAP_USER", "placeholder")
os.environ.setdefault("IMAP_PASSWORD", "placeholder")

import sqlite3
from sqlalchemy import select
from app.db.models import MailAccount, StatementDocument
from app.db.session import get_session_factory
from app.ingestion.service import MailIngestionService

# Temizle
con = sqlite3.connect("dev-local.db")
cur = con.cursor()
cur.execute("DELETE FROM statement_documents")
cur.execute("DELETE FROM emails_ingested")
cur.execute("DELETE FROM mail_ingestion_runs")
con.commit()
con.close()
print("DB temizlendi.\n")

sf = get_session_factory()
with sf() as s:
    acc = s.scalar(select(MailAccount).where(MailAccount.is_active == True).limit(1))  # noqa: E712

# ── 1. Sync ──────────────────────────────────────────────────────────────────
print("=== 1. SYNC ===")
svc = MailIngestionService(mail_account=acc)
s1, _ = svc.run_sync()
print(f"  scanned: {s1['scanned_messages']}")
print(f"  processed: {s1['processed_messages']}")
print(f"  saved_documents: {s1['saved_documents']}")
print(f"  duplicate_messages: {s1['duplicate_messages']}")
print(f"  duplicate_documents: {s1['duplicate_documents']}")

# ── 2. Sync (aynı hesap, aynı mailler) ──────────────────────────────────────
print("\n=== 2. SYNC (aynı hesap) ===")
svc2 = MailIngestionService(mail_account=acc)
s2, _ = svc2.run_sync()
print(f"  scanned: {s2['scanned_messages']}")
print(f"  processed: {s2['processed_messages']}")
print(f"  saved_documents: {s2['saved_documents']}")
print(f"  duplicate_messages: {s2['duplicate_messages']}  (bunlar atlandi)")
print(f"  duplicate_documents: {s2['duplicate_documents']}")

# ── Sonuç ────────────────────────────────────────────────────────────────────
with sf() as s:
    docs = list(s.scalars(select(StatementDocument)).all())
print(f"\nDB'de toplam StatementDocument: {len(docs)} (aynı kalmalı)")
assert len(docs) == s1['saved_documents'], "HATA: duplicate eklendi!"
print("OK — duplicate yok, sistem doğru çalışıyor.")

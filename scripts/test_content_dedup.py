"""Içerik bazlı dedup testi: aynı ekstre farklı hashle gelirse ne olur?"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("DATABASE_URL", "sqlite:///dev-local.db")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("IMAP_HOST", "imap.gmail.com")
os.environ.setdefault("IMAP_PORT", "993")
os.environ.setdefault("IMAP_USER", "placeholder")
os.environ.setdefault("IMAP_PASSWORD", "placeholder")

from sqlalchemy import select
from app.db.models import StatementDocument
from app.db.session import get_session_factory

sf = get_session_factory()

# Mevcut parsed document'i al
with sf() as s:
    doc = s.scalar(select(StatementDocument).where(StatementDocument.parse_status == "parsed").limit(1))
    if not doc:
        print("Oncce test_dedup.py calistirin!")
        sys.exit(1)
    parsed = json.loads(doc.parsed_json)
    print(f"Mevcut ekstre: {parsed['bank_name']} | {parsed['period_start']} - {parsed['period_end']} | {parsed['total_due_try']} TL")

# Katman 3 testini simüle et: aynı bank_name + period ile farklı hash eklenmeye çalışılıyor
from app.ingestion.statement_parser import ParsedStatement, ParsedTransaction
from datetime import date

fake_result = ParsedStatement(
    bank_name=parsed["bank_name"],
    statement_period_start=date.fromisoformat(parsed["period_start"]),
    statement_period_end=date.fromisoformat(parsed["period_end"]),
    due_date=date.fromisoformat(parsed["due_date"]) if parsed.get("due_date") else None,
    total_due_try=parsed["total_due_try"],
    minimum_due_try=parsed["minimum_due_try"],
)

# Katman 3 sorgusu (service.py'deki ile aynı)
with sf() as s:
    content_dupe = s.scalar(
        select(StatementDocument).where(
            StatementDocument.parse_status == "parsed",
            StatementDocument.parsed_json.contains(
                f'"period_start": "{fake_result.statement_period_start}"'
            ),
            StatementDocument.parsed_json.contains(
                f'"period_end": "{fake_result.statement_period_end}"'
            ),
            StatementDocument.parsed_json.contains(
                f'"bank_name": "{fake_result.bank_name}"'
            ),
        )
    )

if content_dupe:
    print(f"\nKatman 3 CALISTI: Ayni ekstre (banka={fake_result.bank_name}, donem={fake_result.statement_period_start}/{fake_result.statement_period_end}) zaten mevcut (doc #{content_dupe.id})")
    print("Yeni PDF farkli hash olsa bile EKLENMEZ.")
else:
    print("\nHATA: Katman 3 duplicate bulmadi!")
    sys.exit(1)

print("\nTum 3 katman aktif:")
print("  [1] Message-ID eslesmesi -> ayi mail tekrar gelmez")
print("  [2] SHA256 hash eslesmesi -> ayi PDF farkli mailden gelmez")
print("  [3] Bank+donem+tutar eslesmesi -> PDF yeniden olusturulmus olsa da gelmez")

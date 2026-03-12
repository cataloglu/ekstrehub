"""Clear ingestion history and re-run sync to trigger fresh PDF parsing."""
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

con = sqlite3.connect("dev-local.db")
cur = con.cursor()
cur.execute("DELETE FROM statement_documents")
cur.execute("DELETE FROM emails_ingested")
cur.execute("DELETE FROM mail_ingestion_runs")
con.commit()
con.close()
print("Cleared old records.")

from sqlalchemy import select

from app.db.models import MailAccount, StatementDocument
from app.db.session import get_session_factory
from app.ingestion.service import MailIngestionService

sf = get_session_factory()
with sf() as session:
    acc = session.scalar(select(MailAccount).where(MailAccount.is_active == True).limit(1))  # noqa: E712

print(f"Syncing: {acc.imap_user}")
svc = MailIngestionService(mail_account=acc)
summary, _ = svc.run_sync()

print("\n=== Summary ===")
for k, v in summary.items():
    print(f"  {k}: {v}")

with sf() as session:
    docs = session.scalars(select(StatementDocument)).all()
    print(f"\n=== Parsed Documents ({len(docs)}) ===")
    for doc in docs:
        print(f"\n  {doc.file_name} | {doc.parse_status} | {doc.file_size_bytes} bytes")
        if doc.parsed_json:
            d = json.loads(doc.parsed_json)
            print(f"  bank: {d.get('bank_name')}")
            print(f"  period: {d.get('period_start')} to {d.get('period_end')}")
            print(f"  due_date: {d.get('due_date')}")
            print(f"  total_due_try: {d.get('total_due_try')}")
            print(f"  minimum_due_try: {d.get('minimum_due_try')}")
            txs = d.get("transactions", [])
            print(f"  transactions: {len(txs)}")
            for tx in txs[:15]:
                sign = "-" if tx["amount"] < 0 else " "
                print(f"    {tx['date']}  {sign}{abs(tx['amount']):>12,.2f} TRY  {tx['description'][:45]}")
            if len(txs) > 15:
                print(f"    ... and {len(txs)-15} more")
            if d.get("parse_notes"):
                print(f"  notes: {d['parse_notes']}")

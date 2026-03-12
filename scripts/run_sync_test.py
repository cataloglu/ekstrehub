"""Run a mail ingestion sync and print results including parsed PDF data."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("DATABASE_URL", "sqlite:///dev-local.db")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("IMAP_HOST", "imap.gmail.com")
os.environ.setdefault("IMAP_PORT", "993")
os.environ.setdefault("IMAP_USER", "placeholder")
os.environ.setdefault("IMAP_PASSWORD", "placeholder")

from sqlalchemy import select

from app.db.models import EmailIngested, MailAccount, StatementDocument
from app.db.session import get_session_factory
from app.ingestion.service import MailIngestionService

sf = get_session_factory()
with sf() as session:
    acc = session.scalar(select(MailAccount).where(MailAccount.is_active == True).limit(1))  # noqa: E712
    if not acc:
        print("ERROR: no active mail account in DB")
        sys.exit(1)
    print(f"Using account: {acc.imap_user} ({acc.imap_host})")

svc = MailIngestionService(mail_account=acc)
summary, was_duplicate = svc.run_sync()
print("\n=== Sync Summary ===")
for k, v in summary.items():
    print(f"  {k}: {v}")

# Print parsed results
with sf() as session:
    docs = session.scalars(select(StatementDocument)).all()
    print(f"\n=== Statement Documents ({len(docs)}) ===")
    for doc in docs:
        print(f"\n  [{doc.id}] {doc.file_name} | type={doc.doc_type} | parse_status={doc.parse_status} | {doc.file_size_bytes} bytes")
        if doc.parsed_json:
            data = json.loads(doc.parsed_json)
            print(f"       bank: {data.get('bank_name')}")
            print(f"       period: {data.get('period_start')} to {data.get('period_end')}")
            print(f"       due_date: {data.get('due_date')}")
            print(f"       total_due_try: {data.get('total_due_try')}")
            print(f"       minimum_due_try: {data.get('minimum_due_try')}")
            txs = data.get("transactions", [])
            print(f"       transactions: {len(txs)}")
            for tx in txs[:10]:
                print(f"         {tx['date']} | {tx['description'][:50]} | {tx['amount']} {tx['currency']}")
            if len(txs) > 10:
                print(f"         ... and {len(txs)-10} more")
            if data.get("parse_notes"):
                print(f"       notes: {data['parse_notes']}")

"""Test LLM parser with the DenizBank PDF already in DB."""
import email
import imaplib
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

from app.db.models import MailAccount
from app.db.session import get_session_factory
from app.ingestion.pdf_extractor import extract_text_from_pdf
from app.ingestion.llm_parser import parse_with_llm

LLM_API_URL = "http://localhost:11434/v1"
LLM_MODEL = "qwen2.5:7b"

# Fetch PDF from IMAP
sf = get_session_factory()
with sf() as session:
    acc = session.scalar(select(MailAccount).where(MailAccount.is_active == True).limit(1))  # noqa: E712

print(f"Fetching PDF from {acc.imap_host} as {acc.imap_user}...")
with imaplib.IMAP4_SSL(acc.imap_host, acc.imap_port) as mail:
    mail.login(acc.imap_user, acc.imap_password)
    mail.select("INBOX")
    _, data = mail.search(None, "ALL")
    pdf_bytes = None
    for uid in reversed(data[0].split()):
        _, fetch_data = mail.fetch(uid, "(RFC822)")
        msg = email.message_from_bytes(fetch_data[0][1])
        if "Ekstre" not in (msg.get("Subject") or ""):
            continue
        for part in msg.walk():
            fname = part.get_filename() or ""
            if fname.lower().endswith(".pdf"):
                pdf_bytes = part.get_payload(decode=True)
                print(f"Found: {fname} ({len(pdf_bytes)} bytes)")
                break
        if pdf_bytes:
            break

if not pdf_bytes:
    print("PDF not found!")
    sys.exit(1)

print("\nExtracting text from PDF...")
text = extract_text_from_pdf(pdf_bytes)
print(f"Extracted {len(text)} chars")

print(f"\nSending to LLM ({LLM_MODEL})...")
print("This may take 30-120 seconds on CPU...")
result, err = parse_with_llm(text, LLM_API_URL, LLM_MODEL, timeout_seconds=300, text_fp="script")

if result is None:
    print(f"LLM parse FAILED ({err or 'unknown'})")
    sys.exit(1)

print("\n=== LLM Parse Result ===")
print(f"bank_name: {result.get('bank_name')}")
print(f"period_start: {result.get('period_start')}")
print(f"period_end: {result.get('period_end')}")
print(f"due_date: {result.get('due_date')}")
print(f"total_due_try: {result.get('total_due_try')}")
print(f"minimum_due_try: {result.get('minimum_due_try')}")
txs = result.get("transactions", [])
print(f"transactions: {len(txs)}")
for tx in txs[:15]:
    sign = "-" if tx.get("amount", 0) < 0 else " "
    print(f"  {tx.get('date')}  {sign}{abs(tx.get('amount',0)):>12,.2f} {tx.get('currency')}  {tx.get('description','')[:50]}")
if len(txs) > 15:
    print(f"  ... and {len(txs)-15} more")

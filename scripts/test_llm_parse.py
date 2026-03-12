"""Test LLM parsing for a specific document ID."""
import sqlite3, json, sys, os, imaplib, email as email_lib
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.ingestion.pdf_extractor import extract_text_from_pdf
from app.ingestion.statement_parser import parse_statement

IMAP_HOST = "imap.gmail.com"
IMAP_USER = "kart@catal.net"
IMAP_PASS = "suhxtaglwjyudrzu"

DOC_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 10

conn = sqlite3.connect("dev-local.db")
row = conn.execute(
    "SELECT sd.file_name, ei.message_id FROM statement_documents sd "
    "JOIN emails_ingested ei ON sd.email_ingested_id = ei.id WHERE sd.id = ?",
    (DOC_ID,)
).fetchone()
conn.close()

if not row:
    print(f"Document {DOC_ID} not found")
    sys.exit(1)

fname, mid = row
print(f"Document {DOC_ID}: {fname} (message_id={mid[:40]}...)")

# Fetch PDF from All Mail
M = imaplib.IMAP4_SSL(IMAP_HOST, 993)
M.login(IMAP_USER, IMAP_PASS)
M.select('"[Gmail]/T\u0026APw-m Postalar"')
typ, data = M.search(None, f'(HEADER Message-ID "{mid}")')
ids = data[0].split()
print(f"Found in Tüm Postalar: {ids}")
if not ids:
    # Try INBOX
    M.select("INBOX")
    typ, data = M.search(None, f'(HEADER Message-ID "{mid}")')
    ids = data[0].split()
    print(f"Found in INBOX: {ids}")

pdf_bytes = None
if ids:
    _, msg_data = M.fetch(ids[0], "(RFC822)")
    msg = email_lib.message_from_bytes(msg_data[0][1])
    pdfs = []
    for part in msg.walk():
        f = part.get_filename() or ""
        if f.lower().endswith(".pdf") or part.get_content_type() == "application/pdf":
            payload = part.get_payload(decode=True)
            if payload:
                pdfs.append((f, payload))
                print(f"  Attachment: {f} ({len(payload)} bytes)")
    # Match by filename
    for f, p in pdfs:
        if f == fname:
            pdf_bytes = p
            break
    if not pdf_bytes and pdfs:
        pdf_bytes = pdfs[0][1]

M.logout()

if not pdf_bytes:
    print("Could not fetch PDF")
    sys.exit(1)

text = extract_text_from_pdf(pdf_bytes)
print(f"\nExtracted text length: {len(text)} chars")
print("--- First 3000 chars ---")
print(text[:3000])

print("\n--- Parsing with LLM (bank_name=None) ---")
result = parse_statement(
    text=text,
    bank_name=None,
    llm_api_url="http://localhost:11434/v1",
    llm_model="qwen2.5:7b",
    llm_timeout_seconds=180,
)
print(f"Bank: {result.bank_name}")
print(f"Period: {result.statement_period_start} → {result.statement_period_end}")
print(f"Due: {result.due_date}")
print(f"Total: {result.total_due_try}")
print(f"Min: {result.minimum_due_try}")
print(f"Card: {result.card_number}")
print(f"Transactions: {len(result.transactions)}")
print(f"Notes: {result.parse_notes}")
for tx in result.transactions[:10]:
    print(f"  {tx.transaction_date} | {tx.description[:40]} | {tx.amount} {tx.currency}")

"""Re-parse only Yapi Kredi documents in the DB using the updated parser."""
import sys, os, io, json, imaplib, email as emaillib, pdfplumber, sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.ingestion.statement_parser import parse_statement

db = sqlite3.connect("dev-local.db")
db.row_factory = sqlite3.Row

# Get IMAP creds
acct = db.execute(
    "SELECT imap_user, imap_host, imap_port, imap_password, mailbox FROM mail_accounts LIMIT 1"
).fetchone()

# Get all YK docs
docs = db.execute(
    "SELECT id, file_name FROM statement_documents WHERE "
    "parsed_json LIKE '%Yapi Kredi%' OR parsed_json LIKE '%Yapı Kredi%'"
).fetchall()
print(f"Found {len(docs)} Yapi Kredi documents to re-parse")

# Connect IMAP
print(f"Connecting {acct['imap_user']} @ {acct['imap_host']}:{acct['imap_port']}")
mail = imaplib.IMAP4_SSL(acct["imap_host"], int(acct["imap_port"]))
mail.login(acct["imap_user"], acct["imap_password"])
mb = acct["mailbox"]
mb_quoted = mb if mb.startswith('"') else f'"{mb}"'
sel_status, _ = mail.select(mb_quoted)
print("SELECT:", sel_status)

typ, data = mail.search(None, "ALL")
all_ids = data[0].split()
print(f"Total messages: {len(all_ids)}")

def fetch_pdf_by_name(target_filename: str):
    """Fetch PDF bytes from IMAP by matching filename."""
    for mid in reversed(all_ids):
        typ, msg_data = mail.fetch(mid, "(RFC822)")
        msg = emaillib.message_from_bytes(msg_data[0][1])
        for part in msg.walk():
            fname = part.get_filename() or ""
            if fname == target_filename:
                return part.get_payload(decode=True)
    return None

for doc in docs:
    doc_id = doc["id"]
    file_name = doc["file_name"]
    print(f"\n--- DOC {doc_id}: {file_name} ---")

    pdf_bytes = fetch_pdf_by_name(file_name)
    if not pdf_bytes:
        print(f"  WARNING: PDF not found in IMAP, skipping")
        continue

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception as e:
        print(f"  ERROR extracting PDF text: {e}")
        continue

    result = parse_statement(text, bank_name="yapi kredi")
    print(f"  bank={result.bank_name} period={result.statement_period_start} -> {result.statement_period_end}")
    print(f"  due={result.due_date} total={result.total_due_try} tx={len(result.transactions)}")

    parsed_json = {
        "bank_name": result.bank_name,
        "card_number": result.card_number,
        "period_start": result.statement_period_start.isoformat() if result.statement_period_start else None,
        "period_end": result.statement_period_end.isoformat() if result.statement_period_end else None,
        "due_date": result.due_date.isoformat() if result.due_date else None,
        "total_due_try": result.total_due_try,
        "minimum_due_try": result.minimum_due_try,
        "parse_notes": result.parse_notes,
        "transactions": [
            {
                "date": tx.transaction_date.isoformat() if tx.transaction_date else None,
                "description": tx.description,
                "amount": tx.amount,
                "currency": tx.currency,
            }
            for tx in result.transactions
        ],
    }

    db.execute(
        "UPDATE statement_documents SET parsed_json=?, parse_status='parsed' WHERE id=?",
        (json.dumps(parsed_json, ensure_ascii=False), doc_id),
    )
    db.commit()
    print(f"  ✓ Updated doc {doc_id}")

mail.logout()
db.close()
print("\nDone.")

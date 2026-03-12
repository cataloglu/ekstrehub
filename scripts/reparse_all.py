"""Re-parse all statement documents from scratch using updated parsers."""
import sys, os, io, json, imaplib, email as emaillib, pdfplumber, sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.ingestion.statement_parser import parse_statement

db = sqlite3.connect("dev-local.db")
db.row_factory = sqlite3.Row

acct = db.execute(
    "SELECT imap_user, imap_host, imap_port, imap_password, mailbox FROM mail_accounts LIMIT 1"
).fetchone()

docs = db.execute("SELECT id, file_name, parsed_json FROM statement_documents ORDER BY id").fetchall()
print(f"Total docs: {len(docs)}")

print(f"Connecting {acct['imap_user']} @ {acct['imap_host']}:{acct['imap_port']}")
mail = imaplib.IMAP4_SSL(acct["imap_host"], int(acct["imap_port"]))
mail.login(acct["imap_user"], acct["imap_password"])
mb = acct["mailbox"]
mb_quoted = mb if mb.startswith('"') else f'"{mb}"'
mail.select(mb_quoted)

typ, data = mail.search(None, "ALL")
all_ids = data[0].split()
print(f"IMAP messages: {len(all_ids)}\n")

# Build a filename -> pdf_bytes cache from IMAP
print("Scanning IMAP for PDF attachments...")
pdf_cache: dict[str, bytes] = {}
for mid in all_ids:
    typ, msg_data = mail.fetch(mid, "(RFC822)")
    msg = emaillib.message_from_bytes(msg_data[0][1])
    for part in msg.walk():
        fname = part.get_filename() or ""
        if fname.lower().endswith(".pdf"):
            payload = part.get_payload(decode=True)
            if payload and fname not in pdf_cache:
                pdf_cache[fname] = payload
print(f"Found {len(pdf_cache)} unique PDFs: {list(pdf_cache.keys())}\n")
mail.logout()

ok = 0
err = 0
for doc in docs:
    doc_id = doc["id"]
    file_name = doc["file_name"]
    # Detect current bank from existing parsed_json for hint
    existing = json.loads(doc["parsed_json"]) if doc["parsed_json"] else {}
    bank_hint = existing.get("bank_name")

    print(f"--- DOC {doc_id}: {file_name}  (was: {bank_hint}) ---")

    pdf_bytes = pdf_cache.get(file_name)
    if not pdf_bytes:
        print(f"  WARNING: PDF not found in IMAP cache, skipping")
        err += 1
        continue

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception as e:
        print(f"  ERROR extracting text: {e}")
        err += 1
        continue

    # Re-detect bank from scratch (no hint) so bank detection is refreshed
    result = parse_statement(text, bank_name=None)
    print(f"  bank={result.bank_name}  period={result.statement_period_start} -> {result.statement_period_end}")
    print(f"  due={result.due_date}  total={result.total_due_try}  tx={len(result.transactions)}  notes={result.parse_notes}")

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
    print(f"  ✓ Saved\n")
    ok += 1

db.close()
print(f"\nDone. {ok} updated, {err} skipped/errors.")

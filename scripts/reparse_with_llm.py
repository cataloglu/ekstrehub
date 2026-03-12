"""Re-parse documents with 0 transactions using LLM (Ollama)."""
import sys, os, io, json, imaplib, email as emaillib, pdfplumber, sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.ingestion.statement_parser import parse_statement

LLM_API_URL = "http://localhost:11434/v1"
LLM_MODEL   = "qwen2.5:7b"
LLM_TIMEOUT = 180  # seconds per document

db = sqlite3.connect("dev-local.db")
db.row_factory = sqlite3.Row

acct = db.execute(
    "SELECT imap_user, imap_host, imap_port, imap_password, mailbox FROM mail_accounts LIMIT 1"
).fetchone()

# Only process documents with 0 transactions
docs = db.execute("""
    SELECT id, file_name, parsed_json
    FROM statement_documents
    WHERE parsed_json IS NOT NULL
      AND (
        json_array_length(json_extract(parsed_json, '$.transactions')) = 0
        OR json_extract(parsed_json, '$.transactions') IS NULL
      )
    ORDER BY id
""").fetchall()

print(f"Documents with 0 transactions: {len(docs)}")
for d in docs:
    p = json.loads(d["parsed_json"]) if d["parsed_json"] else {}
    print(f"  ID={d['id']} bank={p.get('bank_name','?')} file={d['file_name']}")

if not docs:
    print("Nothing to re-parse.")
    db.close()
    sys.exit(0)

# Connect IMAP
print(f"\nConnecting {acct['imap_user']} @ {acct['imap_host']}:{acct['imap_port']}")
mail = imaplib.IMAP4_SSL(acct["imap_host"], int(acct["imap_port"]))
mail.login(acct["imap_user"], acct["imap_password"])
mb = acct["mailbox"]
mb_quoted = mb if mb.startswith('"') else f'"{mb}"'
mail.select(mb_quoted)
typ, data = mail.search(None, "ALL")
all_ids = data[0].split()
print(f"IMAP messages: {len(all_ids)}")

# Build PDF cache
print("Scanning IMAP for PDFs...")
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
mail.logout()
print(f"Found {len(pdf_cache)} PDFs\n")

ok = 0
for doc in docs:
    doc_id = doc["id"]
    file_name = doc["file_name"]
    existing = json.loads(doc["parsed_json"]) if doc["parsed_json"] else {}

    print(f"=== DOC {doc_id}: {file_name} ===")

    pdf_bytes = pdf_cache.get(file_name)
    if not pdf_bytes:
        print(f"  WARNING: PDF not found in IMAP, skipping")
        continue

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception as e:
        print(f"  ERROR extracting PDF: {e}")
        continue

    print(f"  PDF text length: {len(text)} chars")
    print(f"  Sending to LLM ({LLM_MODEL}) — may take 2-3 min on CPU...")

    result = parse_statement(
        text,
        bank_name=None,
        llm_api_url=LLM_API_URL,
        llm_model=LLM_MODEL,
        llm_timeout_seconds=LLM_TIMEOUT,
    )

    print(f"  bank={result.bank_name}  period={result.statement_period_start} -> {result.statement_period_end}")
    print(f"  due={result.due_date}  total={result.total_due_try}  tx={len(result.transactions)}  notes={result.parse_notes}")

    if result.transactions:
        for tx in result.transactions[:5]:
            print(f"    {tx.transaction_date} | {str(tx.description)[:50]} | {tx.amount} {tx.currency}")
        if len(result.transactions) > 5:
            print(f"    ... and {len(result.transactions)-5} more")

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
print(f"Done. {ok}/{len(docs)} documents updated.")

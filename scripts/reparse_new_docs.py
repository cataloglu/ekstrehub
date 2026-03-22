"""Re-parse documents ID>=8 using Tüm Postalar IMAP folder."""
import sqlite3, json, sys, os, imaplib, email as email_lib
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.ingestion.pdf_extractor import extract_text_from_pdf
from app.ingestion.statement_parser import parse_statement, parsed_statement_to_storage_dict
from datetime import date

IMAP_HOST = "imap.gmail.com"
IMAP_USER = "kart@catal.net"
IMAP_PASS = "suhxtaglwjyudrzu"
MAILBOX = '"[Gmail]/T\u0026APw-m Postalar"'  # [Gmail]/Tüm Postalar in IMAP UTF-7


def fetch_pdf(message_id: str, filename: str):
    M = imaplib.IMAP4_SSL(IMAP_HOST, 993)
    M.login(IMAP_USER, IMAP_PASS)
    M.select(MAILBOX)
    typ, data = M.search(None, f'(HEADER Message-ID "{message_id}")')
    ids = data[0].split()
    if not ids:
        M.logout()
        return None, None
    _, msg_data = M.fetch(ids[0], "(RFC822)")
    msg = email_lib.message_from_bytes(msg_data[0][1])
    M.logout()
    # Try to match by filename first, then any PDF
    pdfs = []
    for part in msg.walk():
        fname = part.get_filename() or ""
        if fname.lower().endswith(".pdf") or part.get_content_type() == "application/pdf":
            payload = part.get_payload(decode=True)
            if payload:
                pdfs.append((fname, payload))
    # Match exact filename
    for fname, payload in pdfs:
        if fname == filename:
            return payload, fname
    # Fallback: return first PDF
    if pdfs:
        return pdfs[0][1], pdfs[0][0]
    return None, None


def parsed_to_json(result) -> str:
    return json.dumps(parsed_statement_to_storage_dict(result), ensure_ascii=False)


conn = sqlite3.connect("dev-local.db")
DOC_IDS = list(map(int, sys.argv[1:])) if len(sys.argv) > 1 else None

if DOC_IDS:
    placeholders = ",".join("?" * len(DOC_IDS))
    rows = conn.execute(
        f"SELECT sd.id, sd.file_name, ei.message_id FROM statement_documents sd "
        f"JOIN emails_ingested ei ON sd.email_ingested_id = ei.id WHERE sd.id IN ({placeholders})",
        DOC_IDS
    ).fetchall()
else:
    rows = conn.execute(
        "SELECT sd.id, sd.file_name, ei.message_id FROM statement_documents sd "
        "JOIN emails_ingested ei ON sd.email_ingested_id = ei.id WHERE sd.id >= 8"
    ).fetchall()

print(f"Re-parsing {len(rows)} new document(s)...\n")
for doc_id, fname, mid in rows:
    pdf_bytes, actual_fname = fetch_pdf(mid, fname)
    if not pdf_bytes:
        print(f"ID={doc_id} SKIP: not found in Tüm Postalar")
        continue
    text = extract_text_from_pdf(pdf_bytes)
    # Use LLM as fallback for 0-transaction documents
    parsed = parse_statement(
        text=text,
        bank_name=None,
        llm_api_url="http://localhost:11434/v1",
        llm_model="qwen2.5:7b",
        llm_timeout_seconds=180,
    )
    pjson = parsed_to_json(parsed)
    conn.execute("UPDATE statement_documents SET parsed_json = ? WHERE id = ?", (pjson, doc_id))
    conn.commit()
    print(f"ID={doc_id} FILE={actual_fname} BANK={parsed.bank_name} TX={len(parsed.transactions)} TOTAL={parsed.total_due_try} CARD={parsed.card_number}")

conn.close()
print("\nDone.")

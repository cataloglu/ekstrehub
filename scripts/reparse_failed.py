"""Re-parse failed/empty documents using LLM."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import sqlite3
import imaplib
import email

import app.app_settings as app_settings_module
from app.ingestion.pdf_extractor import extract_text_from_pdf
from app.ingestion.statement_parser import parse_statement

DB_PATH = "dev-local.db"
IMAP_HOST = os.environ.get("IMAP_HOST", "imap.gmail.com")
IMAP_USER = os.environ.get("IMAP_USER", "kart@catal.net")
IMAP_PASS = os.environ.get("IMAP_PASSWORD", "suhxtaglwjyudrzu")

c = sqlite3.connect(DB_PATH)

# Get documents that need re-parsing
rows = c.execute("""
    SELECT sd.id, sd.file_name, sd.email_ingested_id, sd.parse_status, sd.parsed_json
    FROM statement_documents sd
    WHERE sd.parse_status = 'parse_failed'
       OR (sd.parse_status = 'parsed' AND (
           sd.parsed_json IS NULL
           OR json_extract(sd.parsed_json, '$.transactions') = '[]'
           OR json_array_length(json_extract(sd.parsed_json, '$.transactions')) = 0
       ))
    ORDER BY sd.id
""").fetchall()

print(f"Yeniden parse edilecek {len(rows)} dokuman:\n")

llm_cfg = app_settings_module.get_llm_config()
print(f"LLM: {llm_cfg['llm_model']} @ {llm_cfg['llm_api_url']} (timeout={llm_cfg['llm_timeout_seconds']}s)\n")

# Connect to IMAP
imap = imaplib.IMAP4_SSL(IMAP_HOST)
imap.login(IMAP_USER, IMAP_PASS)

def fetch_attachment(email_id_in_db):
    """Fetch the PDF attachment for the given email record."""
    email_row = c.execute(
        "SELECT message_id FROM emails_ingested WHERE id=?", (email_id_in_db,)
    ).fetchone()
    if not email_row:
        return None, None
    msg_id = email_row[0]
    # Search in All Mail
    for folder in ['"[Gmail]/All Mail"', "INBOX", '"[Gmail]/Tum Postalar"', '"Tum Postalar"']:
        try:
            imap.select(folder, readonly=True)
            _, data = imap.search(None, f'HEADER Message-ID "{msg_id}"')
            if data and data[0]:
                uid = data[0].split()[-1]
                _, msg_data = imap.fetch(uid, "(RFC822)")
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)
                for part in msg.walk():
                    if part.get_content_type() == "application/pdf":
                        return part.get_payload(decode=True), part.get_filename()
                break
        except Exception:
            continue
    return None, None

for doc_id, file_name, email_ingested_id, status, parsed_json_str in rows:
    print(f"ID={doc_id} FILE={file_name} STATUS={status}")
    pdf_bytes, fname = fetch_attachment(email_ingested_id)
    if not pdf_bytes:
        print(f"  -> PDF bulunamadi, atlanıyor\n")
        continue

    try:
        text = extract_text_from_pdf(pdf_bytes)
    except Exception as e:
        print(f"  -> PDF metin cıkarma hatası: {e}\n")
        continue

    bank_hint = None
    if parsed_json_str:
        try:
            pj = json.loads(parsed_json_str)
            bank_hint = pj.get("bank_name")
        except Exception:
            pass

    result = parse_statement(
        text,
        bank_hint,
        llm_api_url=llm_cfg["llm_api_url"] if llm_cfg.get("llm_enabled") else "",
        llm_model=llm_cfg["llm_model"],
        llm_api_key=llm_cfg["llm_api_key"],
        llm_timeout_seconds=llm_cfg["llm_timeout_seconds"],
    )

    new_json = json.dumps({
        "bank_name": result.bank_name,
        "card_number": result.card_number,
        "period_start": str(result.statement_period_start) if result.statement_period_start else None,
        "period_end": str(result.statement_period_end) if result.statement_period_end else None,
        "due_date": str(result.due_date) if result.due_date else None,
        "total_due_try": result.total_due_try,
        "minimum_due_try": result.minimum_due_try,
        "transactions": [
            {"date": str(tx.date) if tx.date else None, "description": tx.description, "amount": tx.amount, "currency": tx.currency}
            for tx in result.transactions
        ],
        "parse_notes": result.parse_notes,
    }, ensure_ascii=False)

    new_status = "parsed"
    c.execute(
        "UPDATE statement_documents SET parsed_json=?, parse_status=? WHERE id=?",
        (new_json, new_status, doc_id)
    )
    c.commit()
    print(f"  -> BANK={result.bank_name} TX={len(result.transactions)} TOTAL={result.total_due_try} NOTES={result.parse_notes}\n")

imap.logout()
c.close()
print("Tamamlandi.")

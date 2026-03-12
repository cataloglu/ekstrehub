"""Re-parse statement documents that have parse_status='parsed' but bank='unknown'.

Re-fetches each PDF from Gmail and runs the updated parser chain.
"""
from __future__ import annotations

import imaplib
import email as email_lib
import io
import json
import os
import sqlite3
import sys
from datetime import date

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.ingestion.pdf_extractor import extract_text_from_pdf
from app.ingestion.statement_parser import parse_statement

DB_PATH = os.environ.get("DB_PATH", "dev-local.db")
IMAP_HOST = os.environ.get("IMAP_HOST", "imap.gmail.com")
IMAP_USER = os.environ.get("IMAP_USER", "kart@catal.net")
IMAP_PASS = os.environ.get("IMAP_PASSWORD", "suhxtaglwjyudrzu")
LLM_API_URL = os.environ.get("LLM_API_URL", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen2.5:7b")


def fetch_pdf_from_imap(message_id: str, filename: str) -> bytes | None:
    M = imaplib.IMAP4_SSL(IMAP_HOST, 993)
    M.login(IMAP_USER, IMAP_PASS)
    M.select("INBOX")

    typ, data = M.search(None, f'(HEADER Message-ID "{message_id}")')
    ids = data[0].split()
    if not ids:
        print(f"  NOT FOUND in INBOX: {message_id}")
        M.logout()
        return None

    _, msg_data = M.fetch(ids[0], "(RFC822)")
    msg = email_lib.message_from_bytes(msg_data[0][1])
    M.logout()

    for part in msg.walk():
        ct = part.get_content_type()
        fname = part.get_filename() or ""
        if ct in ("application/pdf", "application/octet-stream") or fname.lower().endswith(".pdf"):
            payload = part.get_payload(decode=True)
            if payload:
                return payload

    # Try inline parts too
    for part in msg.walk():
        payload = part.get_payload(decode=True)
        if payload and len(payload) > 1000:
            return payload

    return None


def _parsed_to_json(result, bank_name: str | None) -> str:
    def _d(d: date | None) -> str | None:
        return d.isoformat() if d else None

    data = {
        "bank_name": result.bank_name,
        "card_number": result.card_number,
        "period_start": _d(result.statement_period_start),
        "period_end": _d(result.statement_period_end),
        "due_date": _d(result.due_date),
        "total_due_try": result.total_due_try,
        "minimum_due_try": result.minimum_due_try,
        "parse_notes": result.parse_notes,
        "transactions": [
            {
                "date": _d(tx.transaction_date),
                "description": tx.description,
                "amount": tx.amount,
                "currency": tx.currency,
            }
            for tx in result.transactions
        ],
    }
    return json.dumps(data, ensure_ascii=False)


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Find documents with unknown bank or no transactions
    rows = conn.execute(
        """
        SELECT sd.id, sd.file_name, sd.parsed_json, ei.message_id
        FROM statement_documents sd
        JOIN emails_ingested ei ON sd.email_ingested_id = ei.id
        WHERE sd.parse_status = 'parsed'
        """
    ).fetchall()

    targets = []
    for row in rows:
        pj = json.loads(row["parsed_json"]) if row["parsed_json"] else {}
        bank = pj.get("bank_name", "unknown")
        tx_count = len(pj.get("transactions", []))
        if bank in ("unknown", None, "") or tx_count == 0:
            targets.append(dict(row))

    print(f"Found {len(targets)} document(s) to re-parse.\n")

    for doc in targets:
        doc_id = doc["id"]
        filename = doc["file_name"]
        message_id = doc["message_id"]
        print(f"[{doc_id}] {filename}  message_id={message_id}")

        pdf_bytes = fetch_pdf_from_imap(message_id, filename)
        if not pdf_bytes:
            print("  Could not fetch PDF, skipping.\n")
            continue

        try:
            text = extract_text_from_pdf(pdf_bytes)
        except Exception as e:
            print(f"  PDF extraction failed: {e}\n")
            continue

        result = parse_statement(
            text=text,
            bank_name=None,
            llm_api_url=LLM_API_URL,
            llm_model=LLM_MODEL,
            llm_timeout_seconds=60,
        )

        parsed_json = _parsed_to_json(result, result.bank_name)

        conn.execute(
            "UPDATE statement_documents SET parsed_json = ?, parse_status = 'parsed' WHERE id = ?",
            (parsed_json, doc_id),
        )
        conn.commit()

        print(f"  bank={result.bank_name}")
        print(f"  period={result.statement_period_start} → {result.statement_period_end}")
        print(f"  due={result.due_date}  total={result.total_due_try}  min={result.minimum_due_try}")
        print(f"  transactions={len(result.transactions)}")
        print(f"  notes={result.parse_notes}\n")

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()

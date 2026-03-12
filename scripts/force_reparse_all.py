"""Force re-parse ALL parsed statement documents to refresh card_number and fix any issues."""
from __future__ import annotations

import json
import os
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scripts.reparse_documents import fetch_pdf_from_imap, _parsed_to_json
from app.ingestion.pdf_extractor import extract_text_from_pdf
from app.ingestion.statement_parser import parse_statement

DB_PATH = os.environ.get("DB_PATH", "dev-local.db")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

rows = conn.execute(
    """
    SELECT sd.id, sd.file_name, sd.parsed_json, ei.message_id
    FROM statement_documents sd
    JOIN emails_ingested ei ON sd.email_ingested_id = ei.id
    WHERE sd.parse_status = 'parsed'
    """
).fetchall()

print(f"Re-parsing {len(rows)} document(s)...\n")

for row in rows:
    existing = json.loads(row["parsed_json"]) if row["parsed_json"] else {}
    existing_bank = existing.get("bank_name")
    print(f"[{row['id']}] {row['file_name']}  existing_bank={existing_bank}")

    pdf = fetch_pdf_from_imap(row["message_id"], row["file_name"])
    if not pdf:
        print("  skipped (could not fetch PDF)\n")
        continue

    text = extract_text_from_pdf(pdf)
    # Pass None to let bank detection run fresh from PDF text
    result = parse_statement(text=text, bank_name=None, llm_api_url="")
    parsed_json = _parsed_to_json(result, result.bank_name)

    conn.execute(
        "UPDATE statement_documents SET parsed_json = ? WHERE id = ?",
        (parsed_json, row["id"]),
    )
    conn.commit()
    print(f"  bank={result.bank_name}  card={result.card_number}  tx={len(result.transactions)}")
    print(f"  period={result.statement_period_start} → {result.statement_period_end}  due={result.due_date}\n")

conn.close()
print("Done.")

"""Delete failed/empty documents and their email records so sync re-processes them."""
import sqlite3, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

c = sqlite3.connect("dev-local.db")

# Find docs that need re-parsing
rows = c.execute("""
    SELECT sd.id, sd.file_name, sd.parse_status, sd.email_ingested_id, sd.parsed_json
    FROM statement_documents sd
    WHERE sd.parse_status = 'parse_failed'
       OR (sd.parse_status = 'parsed' AND (
           sd.parsed_json IS NULL
           OR json_array_length(json_extract(sd.parsed_json, '$.transactions')) = 0
       ))
    ORDER BY sd.id
""").fetchall()

print(f"Yeniden islenmesi gereken {len(rows)} dokuman:\n")
email_ids_to_delete = []
doc_ids_to_delete = []

for doc_id, file_name, status, email_ingested_id, pj in rows:
    p = json.loads(pj) if pj else {}
    bank = p.get("bank_name", "?")
    notes = p.get("parse_notes", [])
    print(f"  ID={doc_id:2d} FILE={file_name:30s} BANK={bank:20s} STATUS={status} NOTES={notes}")
    doc_ids_to_delete.append(doc_id)
    if email_ingested_id:
        email_ids_to_delete.append(email_ingested_id)

print(f"\n{len(doc_ids_to_delete)} dokuman ve {len(email_ids_to_delete)} email kaydi silinecek...")

if doc_ids_to_delete:
    c.execute(f"DELETE FROM statement_documents WHERE id IN ({','.join('?'*len(doc_ids_to_delete))})", doc_ids_to_delete)
if email_ids_to_delete:
    c.execute(f"DELETE FROM emails_ingested WHERE id IN ({','.join('?'*len(email_ids_to_delete))})", email_ids_to_delete)

c.commit()

remaining = c.execute("SELECT COUNT(*) FROM statement_documents").fetchone()[0]
print(f"\nKalan dokuman sayisi: {remaining}")
print("Simdi sync calistirabilirsiniz - silinenleri yeniden indirecek ve parse edecek.")
c.close()

"""Delete 0-tx docs and their email records so sync can re-process them."""
import sqlite3, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

c = sqlite3.connect("dev-local.db")
rows = c.execute("SELECT id, email_ingested_id, parsed_json FROM statement_documents ORDER BY id").fetchall()

to_delete_doc = []
to_delete_email = []
for doc_id, email_id, pj in rows:
    p = json.loads(pj) if pj else {}
    tx_count = len(p.get("transactions", []))
    if tx_count == 0:
        bank = p.get("bank_name", "?")
        print(f"Siliniyor: doc_id={doc_id} email_id={email_id} bank={bank}")
        to_delete_doc.append(doc_id)
        if email_id:
            to_delete_email.append(email_id)

for doc_id in to_delete_doc:
    c.execute("DELETE FROM statement_documents WHERE id=?", (doc_id,))
for email_id in to_delete_email:
    c.execute("DELETE FROM emails_ingested WHERE id=?", (email_id,))
c.commit()
c.close()
print(f"\nSilindi: {len(to_delete_doc)} doc, {len(to_delete_email)} email kaydi")
print("Simdi sync calistirin - silinen belgeler yeniden parse edilecek.")

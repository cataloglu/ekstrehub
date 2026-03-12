"""Fix null bank names in statement_documents."""
import sqlite3, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

c = sqlite3.connect("dev-local.db")

rows = c.execute(
    "SELECT id, parsed_json, email_ingested_id FROM statement_documents WHERE parse_status='parsed' ORDER BY id"
).fetchall()

fixed = 0
for doc_id, pj, email_id in rows:
    p = json.loads(pj) if pj else {}
    if p.get("bank_name") and p["bank_name"] != "null":
        continue  # already has bank name

    # Check email subject for bank hints
    email_row = c.execute(
        "SELECT subject, sender FROM emails_ingested WHERE id=?", (email_id,)
    ).fetchone()
    subj = (email_row[0] or "").lower() if email_row else ""
    sender = (email_row[1] or "").lower() if email_row else ""

    bank = None
    if "isbank" in subj or "is bankasi" in subj or "is bank" in subj or "maximiles" in subj:
        bank = "İş Bankası"
    elif "garanti" in subj:
        bank = "Garanti BBVA"
    elif "denizbank" in subj or "deniz" in subj:
        bank = "DenizBank"
    elif "yapikredi" in subj or "yapi kredi" in subj or "ykb" in subj:
        bank = "Yapı Kredi"
    elif "akbank" in subj:
        bank = "Akbank"
    elif "ziraat" in subj:
        bank = "Ziraat Bankası"
    # Try sender
    elif "isbank" in sender or "garantibbva" in sender:
        bank = "İş Bankası" if "isbank" in sender else "Garanti BBVA"

    print(f"ID={doc_id} bank_name=null | subject='{subj[:60]}' | sender='{sender[:40]}'")
    if bank:
        p["bank_name"] = bank
        new_json = json.dumps(p, ensure_ascii=False)
        c.execute("UPDATE statement_documents SET parsed_json=? WHERE id=?", (new_json, doc_id))
        print(f"  -> Fixed: bank_name={bank}")
        fixed += 1
    else:
        print(f"  -> Could not determine bank from email metadata")

c.commit()
c.close()
print(f"\n{fixed} dokuman duzeltildi.")

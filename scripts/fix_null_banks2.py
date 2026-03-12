"""Fix null bank names by inspecting PDF content keywords."""
import sqlite3, json, sys, imaplib, email as email_mod
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

c = sqlite3.connect("dev-local.db")

rows = c.execute(
    "SELECT id, parsed_json, email_ingested_id FROM statement_documents WHERE parse_status='parsed' ORDER BY id"
).fetchall()

# Look at descriptions in transactions to guess bank
bank_keywords_in_desc = [
    (["MAXIMILES", "MAXIPUANI", "MaxiMiles", "maximilesborcu"], "İş Bankası"),
    (["BONUS", "bonuspuan"], "Garanti BBVA"),
    (["Bonus Card"], "Garanti BBVA"),
    (["WORLD PUAN", "worldpuani"], "Yapı Kredi"),
    (["CARDFINANS", "card finans"], "Yapı Kredi"),
]

for doc_id, pj, email_id in rows:
    p = json.loads(pj) if pj else {}
    if p.get("bank_name") and p["bank_name"] != "null":
        continue

    transactions = p.get("transactions", [])
    all_desc = " ".join(t.get("description", "") for t in transactions).upper()
    
    print(f"ID={doc_id} TX={len(transactions)} card={p.get('card_number')} total={p.get('total_due_try')}")
    # Sample some descriptions
    for t in transactions[:5]:
        print(f"  desc: {t.get('description', '')[:80]}")
    
    bank = None
    for keywords, bank_name in bank_keywords_in_desc:
        if any(kw.upper() in all_desc for kw in keywords):
            bank = bank_name
            break
    
    # Check card prefix
    card = p.get("card_number", "") or ""
    if not bank and card.startswith("4743"):
        bank = "İş Bankası"  # İş Bankası MaxiMiles
    elif not bank and card.startswith("4548"):
        bank = "DenizBank"

    if bank:
        p["bank_name"] = bank
        c.execute("UPDATE statement_documents SET parsed_json=? WHERE id=?", 
                  (json.dumps(p, ensure_ascii=False), doc_id))
        print(f"  -> Fixed: bank_name={bank}\n")
    else:
        print(f"  -> Cannot determine bank\n")

c.commit()
c.close()

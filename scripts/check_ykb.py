import sqlite3, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
c = sqlite3.connect("dev-local.db")
rows = c.execute("SELECT id, email_ingested_id, parsed_json FROM statement_documents ORDER BY id").fetchall()
for r in rows:
    p = json.loads(r[2]) if r[2] else {}
    bank = p.get("bank_name", "NULL") or "NULL"
    if "yap" in bank.lower() or "kredi" in bank.lower():
        email_id = r[1]
        msg_id = c.execute("SELECT message_id FROM emails_ingested WHERE id=?", (email_id,)).fetchone()
        print(f"ID={r[0]} email_id={email_id} msg_id_suffix={str(msg_id[0] if msg_id else '?')[-20:]}")
        print(f"  period_end={p.get('period_end')} card={p.get('card_number')} total={p.get('total_due_try')} tx={len(p.get('transactions',[]))}")
c.close()

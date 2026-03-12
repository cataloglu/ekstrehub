import sqlite3, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
c = sqlite3.connect("dev-local.db")
rows = c.execute("SELECT id, file_name, parsed_json FROM statement_documents ORDER BY id").fetchall()
for r in rows:
    p = json.loads(r[2]) if r[2] else {}
    tx = p.get("transactions", [])
    bank = p.get("bank_name", "?")
    total = p.get("total_due_try")
    ps = p.get("period_start")
    pe = p.get("period_end")
    due = p.get("due_date")
    card = p.get("card_number")
    notes = p.get("parse_notes", [])
    print(f"ID={r[0]:2d} BANK={bank:20s} TX={len(tx):3d} TOTAL={str(total):12s} PERIOD={ps} -> {pe}  DUE={due}  CARD={card}  NOTES={notes}")
c.close()

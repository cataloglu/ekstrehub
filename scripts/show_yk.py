import sqlite3, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
c = sqlite3.connect("dev-local.db")

for doc_id in [8, 9]:
    row = c.execute("SELECT parsed_json FROM statement_documents WHERE id=?", (doc_id,)).fetchone()
    if not row:
        continue
    p = json.loads(row[0])
    print(f"\n=== DOC {doc_id} ===")
    print(f"  bank={p.get('bank_name')} period={p.get('period_start')} -> {p.get('period_end')}")
    print(f"  due={p.get('due_date')} total={p.get('total_due_try')} min={p.get('minimum_due_try')}")
    print(f"  card={p.get('card_number')}")
    print(f"  tx count: {len(p.get('transactions', []))}")
    for tx in p.get("transactions", []):
        print(f"    {tx.get('date')} | {str(tx.get('description',''))[:55]} | {tx.get('amount')} {tx.get('currency')}")

c.close()

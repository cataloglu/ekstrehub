import sqlite3, json

conn = sqlite3.connect("dev-local.db")
cur = conn.cursor()
cur.execute("SELECT id, parsed_json FROM statement_documents WHERE parsed_json IS NOT NULL")

for doc_id, pj in cur.fetchall():
    data = json.loads(pj)
    bank = data.get("bank_name", "?")
    card = data.get("card_number", "?")
    txs = data.get("transactions", [])

    fee_txs = [
        tx for tx in txs
        if any(k in tx.get("description", "").upper()
               for k in ["YILLIK", "BSMV", "KKDF", "FAIZ", "FAİZ", "GECIKME", "AIDAT", "NAKİT AVANS", "NAKITAVANS"])
    ]
    if not fee_txs:
        continue

    period = f"{data.get('period_start','?')} — {data.get('period_end','?')}"
    print(f"\n{'='*70}")
    print(f"  {bank}  |  {card}  |  {period}")
    print(f"{'='*70}")
    for tx in fee_txs:
        print(f"  {tx.get('date','?'):12s}  {tx.get('amount'):>12,.2f} {tx.get('currency','TRY'):3s}  |  {tx.get('description','')}")

conn.close()

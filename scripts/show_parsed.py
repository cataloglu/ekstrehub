import json
import os
import sqlite3
import sys

os.chdir(os.path.join(os.path.dirname(__file__), ".."))

con = sqlite3.connect("dev-local.db")
cur = con.cursor()
cur.execute("SELECT parsed_json FROM statement_documents WHERE parse_status='parsed'")
row = cur.fetchone()
if not row:
    print("No parsed documents found")
    sys.exit(0)

d = json.loads(row[0])
print("bank:", d.get("bank_name"))
print("period_start:", d.get("period_start"))
print("period_end:", d.get("period_end"))
print("due_date:", d.get("due_date"))
print("total_due_try:", d.get("total_due_try"))
print("minimum_due_try:", d.get("minimum_due_try"))
txs = d.get("transactions", [])
print("transactions:", len(txs))
for tx in txs[:20]:
    print(" ", tx["date"], "|", tx["description"][:50], "|", tx["amount"], tx["currency"])
if len(txs) > 20:
    print("  ... and", len(txs) - 20, "more")
print("parse_notes:", d.get("parse_notes"))
con.close()

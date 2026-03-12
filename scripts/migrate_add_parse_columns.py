import sqlite3

con = sqlite3.connect("dev-local.db")
cur = con.cursor()

for stmt in [
    "ALTER TABLE statement_documents ADD COLUMN parse_status TEXT NOT NULL DEFAULT 'pending'",
    "ALTER TABLE statement_documents ADD COLUMN parsed_json TEXT",
]:
    try:
        cur.execute(stmt)
        print(f"OK: {stmt[:60]}")
    except Exception as e:
        print(f"SKIP ({e}): {stmt[:60]}")

con.commit()
con.close()
print("done")

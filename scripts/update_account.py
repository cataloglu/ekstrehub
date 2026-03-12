import sqlite3
conn = sqlite3.connect("dev-local.db")
conn.execute("UPDATE mail_accounts SET imap_password='suhxtaglwjyudrzu' WHERE id=1")
conn.commit()
print("Done:", conn.execute("SELECT imap_password FROM mail_accounts WHERE id=1").fetchone())
conn.close()

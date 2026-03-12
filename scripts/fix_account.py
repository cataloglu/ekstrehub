import sqlite3
conn = sqlite3.connect("dev-local.db")
conn.execute("UPDATE mail_accounts SET imap_host='imap.gmail.com', imap_port=993 WHERE id=1")
conn.commit()
row = conn.execute("SELECT id, account_label, imap_host, imap_port, imap_user, auth_mode FROM mail_accounts WHERE id=1").fetchone()
print("Updated:", row)
conn.close()

"""Extract raw text from Yapı Kredi PDFs via IMAP, save to text files."""
import imaplib, email as emaillib, pdfplumber, io, sys, re, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import sqlite3
db = sqlite3.connect("dev-local.db")
row = db.execute("SELECT imap_user, imap_host, imap_port, auth_mode, imap_password, mailbox FROM mail_accounts LIMIT 1").fetchone()
email_addr, host, port, auth_type, password, mailbox = row
db.close()

print(f"Connecting {email_addr} @ {host}:{port} mailbox={mailbox}")
mail = imaplib.IMAP4_SSL(host, int(port))
mail.login(email_addr, password)

mb = mailbox if mailbox.startswith('"') else f'"{mailbox}"'
sel_status, _ = mail.select(mb)
print("SELECT:", sel_status)

typ, data = mail.search(None, "ALL")
ids = data[0].split()
print(f"Total messages: {len(ids)}")

yk_count = 0
for mid in ids[-100:]:
    typ, msg_data = mail.fetch(mid, "(RFC822)")
    msg = emaillib.message_from_bytes(msg_data[0][1])
    for part in msg.walk():
        fname = part.get_filename() or ""
        if not fname.lower().endswith(".pdf"):
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        try:
            with pdfplumber.open(io.BytesIO(payload)) as pdf:
                text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        except Exception:
            continue
        if "WORLD" not in text.upper() and "YAPI KREDİ" not in text.upper() and "YAPI KREDI" not in text.upper():
            continue
        yk_count += 1
        out_file = f"scripts/yk_raw_{yk_count}.txt"
        with open(out_file, "w", encoding="utf-8", errors="replace") as f:
            f.write(text)
        print(f"\n=== YK PDF #{yk_count}: {fname} -> {out_file} ===")
        # Show key lines
        for line in text.splitlines():
            l = line.strip()
            if any(kw in l.upper() for kw in ["KESIM TARIHI", "ODEME TARIHI", "DÖNEM BORCU", "DONEM BORCU",
                                                "TOPLAM BORÇ", "TOPLAM BORC", "ASGARI", "KART NO", "KART NUMA"]):
                print(f"  KEY: {l}")

mail.logout()
print(f"\nDone. Found {yk_count} YK PDFs.")

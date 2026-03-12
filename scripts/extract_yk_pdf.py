"""Extract raw text from Yapı Kredi PDF via IMAP to debug parser issues."""
import imaplib, email, pdfplumber, io, sys, re, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Load DB to get IMAP credentials
import sqlite3
db = sqlite3.connect("dev-local.db")
row = db.execute("SELECT email_address, imap_host, imap_port, auth_type, password, mailbox FROM mail_accounts LIMIT 1").fetchone()
email_addr, host, port, auth_type, password, mailbox = row
db.close()

print(f"Connecting {email_addr} @ {host}:{port} mailbox={mailbox}")
mail = imaplib.IMAP4_SSL(host, int(port))
mail.login(email_addr, password)

# Quote mailbox
mb = mailbox if mailbox.startswith('"') else f'"{mailbox}"'
sel_status, _ = mail.select(mb)
print("SELECT:", sel_status)

# Search for Yapi Kredi emails
typ, data = mail.search(None, "ALL")
ids = data[0].split()
print(f"Total messages: {len(ids)}, checking last 50...")

yk_pdfs = []
for mid in ids[-50:]:
    typ, msg_data = mail.fetch(mid, "(RFC822)")
    msg = email.message_from_bytes(msg_data[0][1])
    subj = str(msg.get("Subject", ""))
    for part in msg.walk():
        fname = part.get_filename() or ""
        if fname.lower().endswith(".pdf") and ("yapi" in subj.lower() or "world" in subj.lower() or 
                                                "kredi" in subj.lower() or "ekstre" in subj.lower()):
            yk_pdfs.append((subj, fname, part.get_payload(decode=True)))

# Also check by filename
if not yk_pdfs:
    for mid in ids[-50:]:
        typ, msg_data = mail.fetch(mid, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])
        for part in msg.walk():
            fname = part.get_filename() or ""
            if fname.lower().endswith(".pdf"):
                payload = part.get_payload(decode=True)
                if payload:
                    try:
                        with pdfplumber.open(io.BytesIO(payload)) as pdf:
                            text = "\n".join(p.extract_text() or "" for p in pdf.pages[:2])
                        if "WORLD" in text.upper() or "YAPI KREDİ" in text.upper() or "YAPI KREDI" in text.upper():
                            yk_pdfs.append((str(msg.get("Subject", "")), fname, payload))
                    except:
                        pass

print(f"\nFound {len(yk_pdfs)} Yapi Kredi PDFs")
for subj, fname, payload in yk_pdfs[:2]:
    print(f"\n=== {subj[:60]} / {fname} ===")
    with pdfplumber.open(io.BytesIO(payload)) as pdf:
        for pg_i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            print(f"\n--- Page {pg_i+1} ---")
            print(text[:3000])
        total_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    # Look for key patterns
    print("\n--- KEY PATTERNS ---")
    for pat, label in [
        (r"[Kk]esim [Tt]arihi.*", "Hesap Kesim"),
        (r"[Ss]on [Öö]deme.*", "Son Odeme"),
        (r"[Dd]önem [Bb]orcu.*|Donem Borcu.*", "Dönem Borcu"),
        (r"[Tt]oplam [Bb]orc.*|Toplam Borç.*", "Toplam Borç"),
        (r"[Aa]sgari.*|[Mm]inimum.*", "Minimum"),
        (r"\d{2}\.\d{2}\.\d{4}.*\d+[.,]\d+", "TX lines"),
    ]:
        matches = re.findall(pat, total_text)[:5]
        if matches:
            print(f"  {label}: {matches}")

mail.logout()

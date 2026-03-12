"""Test the new İş Bankası slash-format parser."""
import sys, os, io, imaplib, email as emaillib, pdfplumber, sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.ingestion.statement_parser import _parse_isbank

db = sqlite3.connect("dev-local.db")
acct = db.execute(
    "SELECT imap_user, imap_host, imap_port, imap_password, mailbox FROM mail_accounts LIMIT 1"
).fetchone()
db.close()

mail = imaplib.IMAP4_SSL(acct[1], int(acct[2]))
mail.login(acct[0], acct[3])
mb = acct[4]
mb_quoted = mb if mb.startswith('"') else f'"{mb}"'
mail.select(mb_quoted)
typ, data = mail.search(None, "ALL")
all_ids = data[0].split()

pdf_cache: dict[str, bytes] = {}
for mid in all_ids:
    typ, msg_data = mail.fetch(mid, "(RFC822)")
    msg = emaillib.message_from_bytes(msg_data[0][1])
    for part in msg.walk():
        fname = part.get_filename() or ""
        if fname.lower().endswith(".pdf"):
            payload = part.get_payload(decode=True)
            if payload and fname not in pdf_cache:
                pdf_cache[fname] = payload
mail.logout()

for fname in ["document-7.pdf", "document-6.pdf"]:
    pdf_bytes = pdf_cache.get(fname)
    if not pdf_bytes:
        print(f"{fname}: NOT FOUND")
        continue
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    r = _parse_isbank(text)
    print(f"\n=== {fname} ===")
    print(f"  bank={r.bank_name}  period={r.statement_period_start} -> {r.statement_period_end}")
    print(f"  due={r.due_date}  total={r.total_due_try}  min={r.minimum_due_try}")
    print(f"  card={r.card_number}  tx={len(r.transactions)}  notes={r.parse_notes}")
    for tx in r.transactions:
        print(f"  {tx.transaction_date} | {str(tx.description)[:55]:55s} | {tx.amount:>12.2f}")

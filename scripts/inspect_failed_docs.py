"""Inspect raw text of failed documents to understand why parsing fails."""
import sys, os, io, json, imaplib, email as emaillib, pdfplumber, sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

db = sqlite3.connect("dev-local.db")
db.row_factory = sqlite3.Row
acct = db.execute(
    "SELECT imap_user, imap_host, imap_port, imap_password, mailbox FROM mail_accounts LIMIT 1"
).fetchone()

docs = db.execute("""
    SELECT id, file_name FROM statement_documents
    WHERE json_array_length(json_extract(parsed_json, '$.transactions')) = 0
       OR json_extract(parsed_json, '$.transactions') IS NULL
    ORDER BY id
""").fetchall()
db.close()

print(f"Docs with 0 tx: {[(d['id'], d['file_name']) for d in docs]}")

mail = imaplib.IMAP4_SSL(acct["imap_host"], int(acct["imap_port"]))
mail.login(acct["imap_user"], acct["imap_password"])
mb = acct["mailbox"]
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

for doc in docs:
    fname = doc["file_name"]
    pdf_bytes = pdf_cache.get(fname)
    if not pdf_bytes:
        print(f"\nDOC {doc['id']}: NOT FOUND in IMAP")
        continue
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages_text = [p.extract_text() or "" for p in pdf.pages]
            text = "\n".join(pages_text)
    except Exception as e:
        print(f"\nDOC {doc['id']}: PDF error: {e}")
        continue
    print(f"\n{'='*60}")
    print(f"DOC {doc['id']}: {fname} ({len(text)} chars, {len(pages_text)} pages)")
    print(f"{'='*60}")
    # Print first 100 lines
    lines = text.splitlines()
    for i, l in enumerate(lines[:80], 1):
        print(f"{i:3d}: {l}")
    if len(lines) > 80:
        print(f"... ({len(lines)-80} more lines)")

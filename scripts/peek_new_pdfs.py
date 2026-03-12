"""Fetch new PDFs from Gmail and show extracted text to identify bank."""
import imaplib, email, io, sys, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

HOST = "imap.gmail.com"
USER = "kart@catal.net"
PASS = "suhxtaglwjyudrzu"

TARGET_IDS = [
    "<DB6BF774-8275-4729-AE3C-1A428D5BB88F@kayges.com.tr>",
    "<20F982B6-4E53-408B-9CCE-7E2912FC056F@kayges.com.tr>",
]

M = imaplib.IMAP4_SSL(HOST, 993)
M.login(USER, PASS)
M.select("INBOX")

for mid in TARGET_IDS:
    typ, data = M.search(None, f'(HEADER Message-ID "{mid}")')
    ids = data[0].split()
    if not ids:
        print(f"NOT FOUND: {mid}")
        continue
    _, msg_data = M.fetch(ids[0], "(RFC822)")
    msg = email.message_from_bytes(msg_data[0][1])
    for part in msg.walk():
        ct = part.get_content_type()
        fname = part.get_filename() or ""
        if ct == "application/pdf" or fname.lower().endswith(".pdf") or ct == "application/octet-stream":
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            try:
                import pdfplumber
                with pdfplumber.open(io.BytesIO(payload)) as pdf:
                    text = "\n".join(p.extract_text() or "" for p in pdf.pages[:4])
                print(f"=== {fname or 'attachment'} ({len(payload)} bytes) ===")
                print(text[:3000])
                print()
            except Exception as e:
                print(f"PDF error for {fname}: {e}")

M.logout()
print("Done.")

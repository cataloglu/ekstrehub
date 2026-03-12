"""Fetch Yapi Kredi PDF and show extracted text."""
import imaplib, email, io, sys, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pdfplumber

M = imaplib.IMAP4_SSL("imap.gmail.com", 993)
M.login("kart@catal.net", "suhxtaglwjyudrzu")
M.select('"[Gmail]/T&APw-m Postalar"')

TARGET_ID = "<8F832DBF-4F57-4AEF-BF06-980F2058D0F1@kayges.com.tr>"
typ, data = M.search(None, f'(HEADER Message-ID "{TARGET_ID}")')
ids = data[0].split()
print("found:", ids)
if ids:
    _, msg_data = M.fetch(ids[0], "(RFC822)")
    msg = email.message_from_bytes(msg_data[0][1])
    for part in msg.walk():
        fname = part.get_filename() or ""
        if fname.lower().endswith(".pdf") or part.get_content_type() == "application/pdf":
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            print(f"\n=== {fname} ({len(payload)} bytes) ===")
            with pdfplumber.open(io.BytesIO(payload)) as pdf:
                for i, page in enumerate(pdf.pages[:4]):
                    text = page.extract_text() or ""
                    print(f"--- Page {i+1} ---")
                    print(text[:3000])
M.logout()

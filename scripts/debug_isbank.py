"""Debug İş Bankası parser."""
import sys, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import imaplib, email as email_lib, io

HOST = "imap.gmail.com"
USER = "kart@catal.net"
PASS = "suhxtaglwjyudrzu"
MID = "<DB6BF774-8275-4729-AE3C-1A428D5BB88F@kayges.com.tr>"

M = imaplib.IMAP4_SSL(HOST, 993)
M.login(USER, PASS)
M.select("INBOX")
_, data = M.search(None, f'(HEADER Message-ID "{MID}")')
ids = data[0].split()
_, msg_data = M.fetch(ids[0], "(RFC822)")
msg = email_lib.message_from_bytes(msg_data[0][1])
M.logout()

for part in msg.walk():
    ct = part.get_content_type()
    fname = part.get_filename() or ""
    if ct == "application/pdf" or fname.lower().endswith(".pdf"):
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        import pdfplumber
        with pdfplumber.open(io.BytesIO(payload)) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)

        print(f"=== PDF: {fname} ({len(text)} chars) ===")
        print("--- First 1500 chars ---")
        print(text[:1500])
        print()
        print("--- Searching keywords ---")
        for kw in ["hesap kesim tarihi", "son ödeme tarihi", "hesap özeti borcu", "kart numarası"]:
            pos = text.lower().find(kw)
            if pos >= 0:
                print(f"  '{kw}' at pos {pos}: {repr(text[pos:pos+80])}")
            else:
                print(f"  '{kw}' NOT FOUND")

        print()
        print("--- Testing parser ---")
        from app.ingestion.statement_parser import parse_statement, _extract_card_number
        card = _extract_card_number(text)
        print(f"  _extract_card_number → {card}")
        result = parse_statement(text=text, bank_name="Is Bankasi", llm_api_url="")
        print(f"  bank={result.bank_name}  card={result.card_number}")
        print(f"  period={result.statement_period_start} → {result.statement_period_end}")
        print(f"  due={result.due_date}  total={result.total_due_try}")
        print(f"  tx={len(result.transactions)}")
        if result.transactions:
            for tx in result.transactions[:3]:
                print(f"    {tx.transaction_date} | {tx.description[:40]} | {tx.amount}")
        break

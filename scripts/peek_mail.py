"""Peek at the DenizBank statement email to see attachments."""
import imaplib
import email
from email.header import decode_header

conn = imaplib.IMAP4_SSL("imap.gmail.com", 993)
conn.login("kart@catal.net", "suhxtaglwjyudrzu")
conn.select("INBOX")

_, data = conn.search(None, 'ALL')
msg_ids = data[0].split()
print(f"Total messages: {len(msg_ids)}")

for mid in msg_ids:
    _, msg_data = conn.fetch(mid, "(RFC822)")
    msg = email.message_from_bytes(msg_data[0][1])

    subject_raw = msg.get("Subject", "")
    subject_parts = decode_header(subject_raw)
    subject = ""
    for part, enc in subject_parts:
        if isinstance(part, bytes):
            subject += part.decode(enc or "utf-8", errors="replace")
        else:
            subject += part

    sender = msg.get("From", "")

    if "deniz" in subject.lower() or "ekstre" in subject.lower() or "kayges" in sender.lower():
        print(f"\n{'='*60}")
        print(f"From   : {sender}")
        print(f"Subject: {subject}")
        print(f"Date   : {msg.get('Date')}")
        print("Parts:")
        for part in msg.walk():
            ct = part.get_content_type()
            cd = part.get("Content-Disposition", "")
            filename = part.get_filename()
            size = len(part.get_payload(decode=True) or b"")
            print(f"  - {ct} | disposition={cd[:40] if cd else '-'} | filename={filename} | size={size} bytes")

conn.logout()

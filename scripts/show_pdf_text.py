"""Show the exact text pdfplumber extracts from the DenizBank PDF."""
import email
import imaplib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("DATABASE_URL", "sqlite:///dev-local.db")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("IMAP_HOST", "imap.gmail.com")
os.environ.setdefault("IMAP_PORT", "993")
os.environ.setdefault("IMAP_USER", "placeholder")
os.environ.setdefault("IMAP_PASSWORD", "placeholder")

from sqlalchemy import select
from app.db.models import MailAccount
from app.db.session import get_session_factory
from app.ingestion.pdf_extractor import extract_text_from_pdf

sf = get_session_factory()
with sf() as session:
    acc = session.scalar(select(MailAccount).where(MailAccount.is_active == True).limit(1))  # noqa: E712

with imaplib.IMAP4_SSL(acc.imap_host, acc.imap_port) as mail:
    mail.login(acc.imap_user, acc.imap_password)
    mail.select("INBOX")
    _, data = mail.search(None, "ALL")
    for uid in reversed(data[0].split()):
        _, fetch_data = mail.fetch(uid, "(RFC822)")
        msg = email.message_from_bytes(fetch_data[0][1])
        if "Ekstre" not in (msg.get("Subject") or ""):
            continue
        for part in msg.walk():
            fname = part.get_filename() or ""
            if fname.lower().endswith(".pdf"):
                pdf_bytes = part.get_payload(decode=True)
                text = extract_text_from_pdf(pdf_bytes)
                # Write raw text to file to inspect without encoding issues
                with open("debug_pdf_text.txt", "w", encoding="utf-8") as f:
                    f.write(text)
                print(f"Total chars: {len(text)}")
                print(f"Total lines: {len(text.splitlines())}")
                print("\n--- FULL TEXT (first 200 lines) ---")
                for i, line in enumerate(text.splitlines()[:200]):
                    print(f"{i+1:3d}| {repr(line)}")
                break
        break

"""Fetch the DenizBank PDF from IMAP and show extracted text lines."""
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

HOST = acc.imap_host
PORT = acc.imap_port
USER = acc.imap_user
PASS = acc.imap_password

SUBJECT_FRAGMENT = "Ekstre"

print(f"Connecting to {HOST}:{PORT} as {USER} ...")
with imaplib.IMAP4_SSL(HOST, PORT) as mail:
    mail.login(USER, PASS)
    mail.select("INBOX")
    _, data = mail.search(None, "ALL")
    ids = data[0].split()
    print(f"{len(ids)} messages total")

    for uid in reversed(ids):
        _, fetch_data = mail.fetch(uid, "(RFC822)")
        raw = fetch_data[0][1]
        msg = email.message_from_bytes(raw)
        subject = msg.get("Subject", "")
        if SUBJECT_FRAGMENT.lower() not in subject.lower():
            continue
        print(f"\nFound: {subject}")

        for part in msg.walk():
            fname = part.get_filename() or ""
            ct = part.get_content_type() or ""
            if "pdf" not in ct.lower() and not fname.lower().endswith(".pdf"):
                continue
            pdf_bytes = part.get_payload(decode=True)
            if not pdf_bytes:
                continue
            print(f"PDF: {fname} ({len(pdf_bytes)} bytes)")
            text = extract_text_from_pdf(pdf_bytes)
            lines = [l for l in text.splitlines() if l.strip()]
            print(f"\n--- First 80 lines of extracted text ---")
            for i, line in enumerate(lines[:80]):
                print(f"{i+1:3d}| {line}")
            print(f"\n--- Lines 80-120 ---")
            for i, line in enumerate(lines[80:120], start=80):
                print(f"{i+1:3d}| {line}")
        break

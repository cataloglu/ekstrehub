"""Test LLM with the full PDF text and show raw response + finish_reason."""
import email
import imaplib
import json
import os
import sys
import urllib.request

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
        _, fd = mail.fetch(uid, "(RFC822)")
        msg = email.message_from_bytes(fd[0][1])
        if "Ekstre" not in (msg.get("Subject") or ""):
            continue
        for part in msg.walk():
            if (part.get_filename() or "").lower().endswith(".pdf"):
                text = extract_text_from_pdf(part.get_payload(decode=True))
                break
        break

print(f"PDF text: {len(text)} chars, {len(text.splitlines())} lines")

# Only send transaction lines + header to reduce noise
lines = text.splitlines()
# Keep header (first 25 lines) + all transaction lines + last 5 lines
header = lines[:25]
tx_lines = [l for l in lines[25:] if l.strip() and (
    l.strip()[:10].replace("/","").isdigit() or  # starts with date
    "toplam" in l.lower() or
    "d?nem borcu" in l.lower() or
    "asgari" in l.lower()
)]
footer = lines[-5:]
filtered_text = "\n".join(header + ["---transactions---"] + tx_lines + ["---end---"] + footer)
print(f"Filtered text: {len(filtered_text)} chars, {len(filtered_text.splitlines())} lines")
print("\n--- Filtered text preview ---")
for i, l in enumerate(filtered_text.splitlines()[:10]):
    print(f"  {l}")
print(f"  ... ({len(tx_lines)} transaction lines)")

from app.ingestion.llm_parser import _SYSTEM_PROMPT, _USER_PROMPT_TEMPLATE

payload = {
    "model": "qwen2.5:7b",
    "messages": [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _USER_PROMPT_TEMPLATE.format(text=filtered_text)},
    ],
    "temperature": 0.0,
    "max_tokens": 8192,
    "stream": False,
}

print(f"\nSending to LLM... (may take 2-5 min on CPU)")
body = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(
    "http://localhost:11434/v1/chat/completions",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST"
)
with urllib.request.urlopen(req, timeout=600) as resp:
    raw = resp.read().decode("utf-8")

data = json.loads(raw)
content = data["choices"][0]["message"]["content"]
finish = data["choices"][0].get("finish_reason")
print(f"\nfinish_reason: {finish}")
print(f"response length: {len(content)} chars")

try:
    c = content.strip()
    if c.startswith("```"):
        c = c.split("```")[1].lstrip("json").strip()
    parsed = json.loads(c)
    txs = parsed.get("transactions", [])
    print(f"\nbank: {parsed.get('bank_name')}")
    print(f"period: {parsed.get('period_start')} to {parsed.get('period_end')}")
    print(f"due_date: {parsed.get('due_date')}")
    print(f"total_due_try: {parsed.get('total_due_try')}")
    print(f"transactions: {len(txs)}")
    for tx in txs[:20]:
        print(f"  {tx['date']}  {tx['amount']:>12,.2f} {tx['currency']}  {tx['description'][:50]}")
    if len(txs) > 20:
        print(f"  ... and {len(txs)-20} more")
except Exception as e:
    print(f"JSON parse error: {e}")
    print("Raw content (first 1000 chars):")
    print(content[:1000])

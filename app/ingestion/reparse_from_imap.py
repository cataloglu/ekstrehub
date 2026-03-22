"""Re-fetch PDFs from IMAP and re-run the statement parser (e.g. after enabling LLM)."""
from __future__ import annotations

import email as email_lib
import imaplib
import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import EmailIngested, MailAccount, StatementDocument
from app.ingestion.gmail_oauth import refresh_access_token
from app.ingestion.learned_rules import load_learned_rule_dict, maybe_train_learned_rules
from app.ingestion.pdf_extractor import extract_text_from_pdf
from app.ingestion.runtime_config import runtime_from_mail_account
from app.ingestion.bank_identification import canonical_bank_name, normalize_bank_name
from app.ingestion.statement_parser import (
    is_false_fintech_bank_name,
    is_llm_failure_empty,
    parse_statement,
    parsed_statement_to_storage_dict,
    resolve_bank_hint,
)
import app.app_settings as app_settings_module

log = logging.getLogger(__name__)

# Try primary mailbox first, then common Gmail folders (same idea as scripts/reparse_failed.py)
_FALLBACK_MAILBOXES = (
    "[Gmail]/All Mail",
    "INBOX",
    "[Gmail]/Promotions",
    "[Gmail]/Spam",
)


def _quote_mailbox(name: str) -> str:
    if " " in name or name.startswith("["):
        escaped = name.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return name


def _imap_login(mail_account: MailAccount) -> imaplib.IMAP4_SSL:
    settings = get_settings()
    runtime = runtime_from_mail_account(mail_account)
    mail = imaplib.IMAP4_SSL(runtime.imap_host, int(runtime.imap_port))
    if runtime.auth_mode == "oauth_gmail":
        token = mail_account.oauth_refresh_token or ""
        access = refresh_access_token(settings, token)
        auth_string = f"user={runtime.imap_user}\x01auth=Bearer {access}\x01\x01"
        mail.authenticate("XOAUTH2", lambda _: auth_string.encode("utf-8"))
    else:
        mail.login(runtime.imap_user, runtime.imap_password)
    return mail


def _extract_pdf_from_rfc822(raw: bytes, file_name_hint: str) -> bytes | None:
    msg = email_lib.message_from_bytes(raw)
    hint_lower = (file_name_hint or "").lower()
    first_pdf: bytes | None = None
    for part in msg.walk():
        fn = (part.get_filename() or "").strip()
        ct = (part.get_content_type() or "").lower()
        if ct == "application/pdf" or fn.lower().endswith(".pdf"):
            payload = part.get_payload(decode=True)
            if payload and len(payload) > 100:
                if hint_lower and fn.lower() == hint_lower:
                    return payload
                if first_pdf is None:
                    first_pdf = payload
    return first_pdf


def fetch_pdf_for_document(
    mail: imaplib.IMAP4_SSL,
    mail_account: MailAccount,
    message_id: str,
    file_name: str,
) -> bytes | None:
    """Locate message by Message-ID across mailboxes; return PDF bytes."""
    mid = (message_id or "").strip()
    if not mid:
        return None

    primary = (mail_account.mailbox or "INBOX").strip()
    folders = [primary] + [f for f in _FALLBACK_MAILBOXES if f != primary]
    seen: set[str] = set()
    ordered: list[str] = []
    for f in folders:
        if f not in seen:
            seen.add(f)
            ordered.append(f)

    crit = f'HEADER Message-ID "{mid}"'
    for folder in ordered:
        try:
            mb = _quote_mailbox(folder)
            st, _ = mail.select(mb, readonly=True)
            if st != "OK":
                continue
            typ, data = mail.search(None, crit)
            if typ != "OK" or not data or not data[0]:
                continue
            uids = data[0].split()
            if not uids:
                continue
            uid = uids[-1]
            typ, msg_data = mail.fetch(uid, "(RFC822)")
            if typ != "OK" or not msg_data or not isinstance(msg_data[0], tuple):
                continue
            raw = msg_data[0][1]
            if isinstance(raw, int):
                continue
            pdf = _extract_pdf_from_rfc822(raw, file_name)
            if pdf:
                return pdf
        except Exception as exc:
            log.debug("fetch_pdf folder=%s err=%s", folder, exc)
            continue
    return None


def fetch_pdf_bytes_for_statement(
    session: Session,
    doc_id: int,
) -> tuple[bytes | None, str, str | None]:
    """Load PDF bytes from IMAP for a stored statement (same source as reparse).

    Returns (pdf_bytes, error_code, file_name). error_code is empty string on success.
    """
    doc = session.get(StatementDocument, doc_id)
    if not doc or doc.doc_type != "pdf":
        return None, "not_found_or_not_pdf", None
    email_row = session.get(EmailIngested, doc.email_ingested_id)
    if not email_row or not email_row.mail_account_id:
        return None, "email_or_account_missing", None
    acct = session.get(MailAccount, email_row.mail_account_id)
    if not acct or not acct.is_active:
        return None, "mail_account_missing", None
    if not (email_row.message_id or "").strip():
        return None, "no_message_id", None

    mail = _imap_login(acct)
    try:
        pdf = fetch_pdf_for_document(mail, acct, email_row.message_id, doc.file_name)
    finally:
        try:
            mail.logout()
        except Exception:
            pass
    if not pdf:
        return None, "pdf_not_found_in_imap", None
    fname = doc.file_name or f"ekstre-{doc_id}.pdf"
    return pdf, "", fname


def _result_to_json(result: Any) -> str:
    return json.dumps(parsed_statement_to_storage_dict(result), ensure_ascii=False)


def _coalesce_reparse_bank_hint(pj_bank: str | None, email_bank: str | None) -> str | None:
    """Prefer real issuer from JSON; if JSON is Param/Papara, use mail bank when it is real."""
    pj_c = canonical_bank_name(normalize_bank_name(pj_bank)) if pj_bank else None
    em_c = canonical_bank_name(normalize_bank_name(email_bank)) if email_bank else None
    if pj_c and not is_false_fintech_bank_name(pj_bank):
        return pj_c
    if em_c and not is_false_fintech_bank_name(email_bank):
        return em_c
    if pj_c:
        return pj_c
    return em_c


def reparse_one_pdf_document(session: Session, doc: StatementDocument, mail: imaplib.IMAP4_SSL) -> dict[str, Any]:
    """Re-parse a single PDF statement document. Caller holds IMAP connection and mail_account."""
    email_row = session.get(EmailIngested, doc.email_ingested_id)
    if not email_row or not email_row.mail_account_id:
        return {"doc_id": doc.id, "ok": False, "error": "email_or_account_missing"}

    acct = session.get(MailAccount, email_row.mail_account_id)
    if not acct or not acct.is_active:
        return {"doc_id": doc.id, "ok": False, "error": "mail_account_missing"}

    pdf = fetch_pdf_for_document(mail, acct, email_row.message_id, doc.file_name)
    if not pdf:
        return {"doc_id": doc.id, "ok": False, "error": "pdf_not_found_in_imap"}

    try:
        text = extract_text_from_pdf(pdf)
    except Exception as exc:
        return {"doc_id": doc.id, "ok": False, "error": f"pdf_extract_failed:{exc}"}

    pj_bank: str | None = None
    if doc.parsed_json:
        try:
            pj = json.loads(doc.parsed_json)
            pj_bank = pj.get("bank_name")
        except Exception:
            pass
    bank_hint = _coalesce_reparse_bank_hint(pj_bank, email_row.bank_name)

    # Learned rules key must not use stale "Param" — same resolution as parse_statement
    bank_for_rules = resolve_bank_hint(bank_hint, text)
    learned = load_learned_rule_dict(session, bank_for_rules)

    llm = app_settings_module.get_llm_config()
    llm_url = llm["llm_api_url"] if llm.get("llm_enabled") else ""

    result = parse_statement(
        text,
        bank_hint,
        llm_api_url=llm_url,
        llm_model=llm["llm_model"],
        llm_api_key=llm["llm_api_key"],
        llm_timeout_seconds=int(llm.get("llm_timeout_seconds", 120)),
        llm_min_tx_threshold=int(llm.get("llm_min_tx_threshold", 0)),
        learned_rules=learned,
    )
    if (
        result
        and "llm_parsed" in (result.parse_notes or [])
        and len(result.transactions) > 0
    ):
        maybe_train_learned_rules(session, result.bank_name or bank_for_rules, text, result, llm)

    doc.parsed_json = _result_to_json(result)
    if is_llm_failure_empty(result):
        doc.parse_status = "parse_failed"
    else:
        doc.parse_status = "parsed"
    session.commit()

    if is_llm_failure_empty(result):
        err = "llm_timeout" if "llm_timeout" in (result.parse_notes or []) else "llm_failed"
        return {
            "doc_id": doc.id,
            "ok": False,
            "error": err,
            "bank_name": result.bank_name,
            "transaction_count": 0,
            "parse_notes": result.parse_notes,
        }

    return {
        "doc_id": doc.id,
        "ok": True,
        "bank_name": result.bank_name,
        "transaction_count": len(result.transactions),
        "parse_notes": result.parse_notes,
    }


def collect_doc_ids_for_scope(session: Session, scope: str, doc_ids: list[int]) -> list[int]:
    """Return statement document IDs to re-parse."""
    if scope == "selected":
        if not doc_ids:
            return []
        rows = session.scalars(
            select(StatementDocument.id).where(StatementDocument.id.in_(doc_ids))
        ).all()
        return list(rows)

    if scope == "failed":
        rows = session.scalars(
            select(StatementDocument.id)
            .where(StatementDocument.doc_type == "pdf")
            .where(StatementDocument.parse_status == "parse_failed")
            .order_by(StatementDocument.id)
        ).all()
        return list(rows)

    if scope == "empty":
        # Parsed but no transactions (or LLM notes), or parse_failed
        candidates = session.scalars(select(StatementDocument).where(StatementDocument.doc_type == "pdf")).all()
        out: list[int] = []
        for d in candidates:
            if d.parse_status == "parse_failed":
                out.append(d.id)
                continue
            if d.parse_status != "parsed":
                continue
            n = 0
            notes: list[str] = []
            if d.parsed_json:
                try:
                    pj = json.loads(d.parsed_json)
                    n = len(pj.get("transactions") or [])
                    notes = pj.get("parse_notes") or []
                except Exception:
                    n = 0
            if (
                n == 0
                or "llm_timeout" in notes
                or "llm_failed" in notes
                or "no_transactions_found" in notes
                or "llm_required" in notes  # eski kayıtlar
            ):
                out.append(d.id)
        return out

    if scope == "all_pdf":
        rows = session.scalars(
            select(StatementDocument.id)
            .where(StatementDocument.doc_type == "pdf")
            .order_by(StatementDocument.id)
        ).all()
        return list(rows)

    return []


def run_batch_reparse(scope: str, doc_ids: list[int], max_docs: int = 40) -> dict[str, Any]:
    """Run re-parse in a blocking batch (call from thread pool)."""
    from app.db.session import get_session_factory

    cfg = app_settings_module.get_llm_config()
    if not cfg.get("llm_enabled") or not (cfg.get("llm_api_url") or "").strip():
        return {
            "ok": False,
            "error": "llm_not_configured",
            "message": "AI parser açık ve LLM API URL dolu olmalı (Ayarlar → AI Parser).",
        }

    session_factory = get_session_factory()
    with session_factory() as session:
        ids = collect_doc_ids_for_scope(session, scope, doc_ids)
        ids = ids[:max_docs]

    if not ids:
        return {"ok": True, "processed": 0, "skipped": 0, "results": [], "message": "Uygun PDF ekstre bulunamadı."}

    # Group by mail account to reuse IMAP connections
    from collections import defaultdict

    session_factory = get_session_factory()
    with session_factory() as session:
        by_account: dict[int, list[StatementDocument]] = defaultdict(list)
        for doc_id in ids:
            doc = session.get(StatementDocument, doc_id)
            if not doc or doc.doc_type != "pdf":
                continue
            email_row = session.get(EmailIngested, doc.email_ingested_id)
            if not email_row or not email_row.mail_account_id:
                continue
            by_account[email_row.mail_account_id].append(doc)

    results: list[dict[str, Any]] = []
    for acct_id, docs in by_account.items():
        with session_factory() as session:
            acct = session.get(MailAccount, acct_id)
            if not acct:
                for d in docs:
                    results.append({"doc_id": d.id, "ok": False, "error": "account_gone"})
                continue
        mail = _imap_login(acct)
        try:
            for doc in docs:
                # Re-load doc in fresh session for update
                with session_factory() as session:
                    d = session.get(StatementDocument, doc.id)
                    if not d:
                        results.append({"doc_id": doc.id, "ok": False, "error": "doc_gone"})
                        continue
                    try:
                        r = reparse_one_pdf_document(session, d, mail)
                        results.append(r)
                    except Exception as exc:
                        log.exception("reparse doc %s", doc.id)
                        results.append({"doc_id": doc.id, "ok": False, "error": str(exc)})
        finally:
            try:
                mail.logout()
            except Exception:
                pass

    # Docs skipped above (no mail account etc.) must still return an error row — else UI shows nothing
    scheduled_ids = {d.id for docs in by_account.values() for d in docs}
    for doc_id in ids:
        if doc_id in scheduled_ids:
            continue
        with session_factory() as session:
            doc = session.get(StatementDocument, doc_id)
            if not doc:
                results.append({"doc_id": doc_id, "ok": False, "error": "doc_gone"})
            elif doc.doc_type != "pdf":
                results.append({"doc_id": doc_id, "ok": False, "error": "not_pdf"})
            else:
                results.append({"doc_id": doc_id, "ok": False, "error": "email_or_account_missing"})

    ok_n = sum(1 for r in results if r.get("ok"))
    return {
        "ok": True,
        "processed": len(results),
        "succeeded": ok_n,
        "failed": len(results) - ok_n,
        "results": results,
    }

"""Clear ingestion-related DB rows (mail accounts & LLM settings are kept)."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import delete, func, select

from app.db.models import (
    AuditLog,
    EmailIngested,
    LearnedParserRule,
    MailIngestionRun,
    StatementDocument,
)

log = logging.getLogger(__name__)

# UI must send this exact string (case-sensitive).
RESET_CONFIRM_PHRASE = "SIFIRLA"

# Test: drop only learned regex rows (ekstreler kalır; sonraki parse LLM’e gider).
CLEAR_LEARNED_RULES_CONFIRM_PHRASE = "KURALLAR"


def reset_ingestion_data(session) -> dict[str, Any]:
    """Delete statements, mail ingestion history, learned rules, audit logs. Returns counts deleted."""
    counts: dict[str, int] = {
        "statement_documents": session.scalar(select(func.count()).select_from(StatementDocument)) or 0,
        "emails_ingested": session.scalar(select(func.count()).select_from(EmailIngested)) or 0,
        "mail_ingestion_runs": session.scalar(select(func.count()).select_from(MailIngestionRun)) or 0,
        "learned_parser_rules": session.scalar(select(func.count()).select_from(LearnedParserRule)) or 0,
        "audit_logs": session.scalar(select(func.count()).select_from(AuditLog)) or 0,
    }

    # Children first (explicit; works on all backends)
    session.execute(delete(StatementDocument))
    session.execute(delete(EmailIngested))
    session.execute(delete(MailIngestionRun))
    session.execute(delete(LearnedParserRule))
    session.execute(delete(AuditLog))
    session.commit()

    log.info(
        "system_reset_ingestion_done deleted=%s",
        counts,
    )
    return {"ok": True, "deleted": counts}


def clear_learned_parser_rules(session) -> dict[str, Any]:
    """Delete all rows from learned_parser_rules. Ekstre / mail kayıtları dokunulmaz."""
    n = session.scalar(select(func.count()).select_from(LearnedParserRule)) or 0
    session.execute(delete(LearnedParserRule))
    session.commit()
    log.info("learned_parser_rules_cleared count=%d", n)
    return {"ok": True, "deleted_learned_parser_rules": n}

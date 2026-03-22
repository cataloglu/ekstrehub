"""Statement parser — learned regex first (per bank), then LLM.

If a bank has stored regex rules from a prior successful LLM parse, those run locally (no API).
Otherwise PDF text goes to the configured LLM. A minimal fallback is used if LLM is unreachable.
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.ingestion.bank_identification import (
    canonical_bank_name,
    normalize_bank_name,
    normalize_optional_llm_str,
)

log = logging.getLogger(__name__)

# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class ParsedTransaction:
    date: date | None = None
    description: str = ""
    amount: float = 0.0
    currency: str = "TRY"


@dataclass
class ParsedStatement:
    bank_name: str | None = None
    card_number: str | None = None
    statement_period_start: date | None = None
    statement_period_end: date | None = None
    due_date: date | None = None
    total_due_try: float | None = None
    minimum_due_try: float | None = None
    transactions: list[ParsedTransaction] = field(default_factory=list)
    parse_notes: list[str] = field(default_factory=list)
    # Notices from PDF (Pazarama/MaxiMil expiry, legal warnings, etc.)
    statement_reminders: list[dict[str, Any]] = field(default_factory=list)


def parsed_statement_to_storage_dict(ps: ParsedStatement) -> dict[str, Any]:
    """JSON-serializable dict for `statement_documents.parsed_json`."""
    return {
        "bank_name": ps.bank_name,
        "card_number": ps.card_number,
        "period_start": str(ps.statement_period_start) if ps.statement_period_start else None,
        "period_end": str(ps.statement_period_end) if ps.statement_period_end else None,
        "due_date": str(ps.due_date) if ps.due_date else None,
        "total_due_try": ps.total_due_try,
        "minimum_due_try": ps.minimum_due_try,
        "transactions": [
            {
                "date": str(tx.date) if tx.date else None,
                "description": tx.description,
                "amount": tx.amount,
                "currency": tx.currency,
            }
            for tx in ps.transactions
        ],
        "parse_notes": ps.parse_notes,
        "statement_reminders": ps.statement_reminders or [],
    }


def _attach_statement_reminders(ps: ParsedStatement, text: str) -> None:
    """Fill statement_reminders from raw PDF text (not from LLM JSON)."""
    from app.ingestion.statement_reminders import extract_statement_reminders

    ps.statement_reminders = extract_statement_reminders(text)


def is_llm_failure_empty(ps: ParsedStatement) -> bool:
    """True when LLM was attempted but produced no transactions (timeout / API error)."""
    if ps.transactions:
        return False
    notes = ps.parse_notes or []
    return "llm_timeout" in notes or "llm_failed" in notes


# ── Bank detection (for logging/context only, no parsing rules) ───────────────

_BANK_KEYWORDS: list[tuple[str, str]] = [
    ("denizbank", "DenizBank"),
    ("garanti", "Garanti BBVA"),
    ("yapı kredi", "Yapı Kredi"),
    ("yapikredi", "Yapı Kredi"),
    ("ykb", "Yapı Kredi"),
    ("akbank", "Akbank"),
    ("ziraat", "Ziraat Bankası"),
    ("vakıfbank", "VakıfBank"),
    ("vakifbank", "VakıfBank"),
    ("halkbank", "Halkbank"),
    ("iş bankası", "İş Bankası"),
    ("isbank", "İş Bankası"),
    ("işbank", "İş Bankası"),
    ("türkiye iş", "İş Bankası"),
    ("maximiles", "İş Bankası"),
    ("maxipuan", "İş Bankası"),
    ("qnb", "QNB Finansbank"),
    ("finansbank", "QNB Finansbank"),
    ("teb", "TEB"),
    ("hsbc", "HSBC"),
    ("enpara", "QNB Finansbank"),
    ("ing bank", "ING Bank"),
    ("ingbank", "ING Bank"),
    ("param", "Param"),
    ("papara", "Papara"),
]


def _detect_bank_from_text(text: str) -> str | None:
    """Detect bank name from PDF text for context/logging. Returns None if unknown."""
    lower = text.lower()
    for keyword, name in _BANK_KEYWORDS:
        # "param" is a substring of "parametre", "parametrik", etc. — require whole word.
        if keyword == "param":
            if re.search(r"\bparam\b", lower) is None:
                continue
            return name
        if keyword in lower:
            return name
    return None


# LLM often labels the *merchant* "Param" (POS/wallet) as bank_name on real bank statements.
_FINTECH_FALSE_BANKS = frozenset({"param", "papara"})


def is_false_fintech_bank_name(name: str | None) -> bool:
    """True if *name* normalizes to Param/Papara — not a real card-issuer hint."""
    n = canonical_bank_name(normalize_bank_name(name))
    return bool(n and n.lower() in _FINTECH_FALSE_BANKS)


def resolve_bank_hint(bank_name: str | None, text: str) -> str | None:
    """Normalize email/JSON bank hint; ignore Param/Papara; fall back to PDF keyword detection."""
    n = canonical_bank_name(normalize_bank_name(bank_name))
    if n and n.lower() in _FINTECH_FALSE_BANKS:
        log.info("bank_hint_fintech_trap_cleared bank_in=%s", bank_name)
        n = None
    if not n:
        n = canonical_bank_name(_detect_bank_from_text(text))
    return n


def _reconcile_llm_bank_name(
    llm_bank: str | None,
    text: str,
    hint_bank: str | None,
) -> str | None:
    """If LLM says Param/Papara but email/PDF clearly names a real bank, prefer that bank."""
    n = canonical_bank_name(normalize_bank_name(llm_bank))
    if not n:
        return None
    low = n.lower()
    if low not in _FINTECH_FALSE_BANKS:
        return n
    hint = canonical_bank_name(normalize_bank_name(hint_bank))
    if hint and hint.lower() not in _FINTECH_FALSE_BANKS:
        log.info("bank_reconcile_fintech_trap prefer_hint llm=%s -> %s", n, hint)
        return hint
    detected = canonical_bank_name(_detect_bank_from_text(text))
    if detected and detected.lower() not in _FINTECH_FALSE_BANKS:
        log.info("bank_reconcile_fintech_trap prefer_text llm=%s -> %s", n, detected)
        return detected
    return n


# ── LLM result → ParsedStatement conversion ───────────────────────────────────

def _parse_date(val: Any) -> date | None:
    if not val:
        return None
    try:
        from datetime import datetime
        return datetime.strptime(str(val).strip()[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _parse_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except Exception:
        return None


def _llm_result_to_parsed_statement(data: dict[str, Any]) -> ParsedStatement:
    """Convert the LLM's JSON output to a ParsedStatement."""
    ps = ParsedStatement()
    ps.bank_name = canonical_bank_name(normalize_bank_name(data.get("bank_name")))
    ps.card_number = normalize_optional_llm_str(data.get("card_number"))
    ps.statement_period_start = _parse_date(data.get("period_start"))
    ps.statement_period_end = _parse_date(data.get("period_end"))
    ps.due_date = _parse_date(data.get("due_date"))
    ps.total_due_try = _parse_float(data.get("total_due_try"))
    ps.minimum_due_try = _parse_float(data.get("minimum_due_try"))
    ps.parse_notes = ["llm_parsed"]

    for tx in data.get("transactions", []):
        t = ParsedTransaction()
        t.date = _parse_date(tx.get("date"))
        t.description = str(tx.get("description") or "").strip()
        t.amount = float(tx.get("amount") or 0)
        t.currency = str(tx.get("currency") or "TRY").upper()
        ps.transactions.append(t)

    if not ps.transactions:
        ps.parse_notes.append("no_transactions_found")

    return ps


# ── Card number extraction (used for display, LLM may also provide it) ────────

_CARD_RE = re.compile(
    r"(\d{4}[\s*-]*\*{4,8}[\s*-]*\*{4,8}[\s*-]*\d{4}"
    r"|\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4})",
    re.IGNORECASE,
)


def _text_fingerprint(text: str) -> str:
    """Short hash for log correlation (same PDF → same fp)."""
    if not text:
        return "0"
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _extract_card_number(text: str) -> str | None:
    m = _CARD_RE.search(text[:3000])
    if m:
        raw = m.group(0)
        digits_and_stars = re.sub(r"[\s-]", "", raw)
        if len(digits_and_stars) >= 16:
            return digits_and_stars[:16]
    return None


# ── Main entry point ──────────────────────────────────────────────────────────

def parse_statement(
    text: str,
    bank_name: str | None,
    llm_api_url: str = "",
    llm_model: str = "gpt-4o-mini",
    llm_api_key: str = "",
    llm_timeout_seconds: int = 180,
    llm_min_tx_threshold: int = 0,
    learned_rules: dict[str, Any] | None = None,
    skip_learned_rules: bool = False,
) -> ParsedStatement:
    """Parse statement text: optional learned local regex, then LLM.

    Args:
        learned_rules: JSON rules from DB for this bank (regex trained after prior LLM success).
        skip_learned_rules: If True, skip local rules and go straight to LLM.
        llm_min_tx_threshold: Kept for API compatibility.
    """
    text_fp = _text_fingerprint(text)
    bank_in = bank_name
    # Param/Papara in DB/email JSON is not a real issuer — detect from PDF text instead
    bank_name = resolve_bank_hint(bank_name, text)

    if bank_name:
        log.info("bank_identified bank=%s", bank_name)

    log.info(
        "parser_parse_start text_fp=%s text_len=%d bank_in=%s bank=%s "
        "learned_rules=%s skip_learned=%s llm_timeout=%ds",
        text_fp,
        len(text),
        bank_in,
        bank_name,
        bool(learned_rules),
        skip_learned_rules,
        llm_timeout_seconds,
    )

    # ── Learned local rules (no API) ───────────────────────────────────────────
    if learned_rules and not skip_learned_rules:
        from app.ingestion.learned_rules import try_apply_learned_rules

        local = try_apply_learned_rules(text, learned_rules, bank_name, text_fp=text_fp)
        if local and len(local.transactions) >= 1:
            log.info(
                "learned_local_parse_ok bank=%s tx=%d text_fp=%s",
                bank_name,
                len(local.transactions),
                text_fp,
            )
            log.info(
                "parser_parse_done path=learned_local bank=%s tx=%d notes=%s text_fp=%s",
                local.bank_name,
                len(local.transactions),
                local.parse_notes,
                text_fp,
            )
            _attach_statement_reminders(local, text)
            return local
        log.info(
            "learned_local_not_applied bank=%s falling_back_to_llm text_fp=%s",
            bank_name,
            text_fp,
        )

    # ── LLM parsing ───────────────────────────────────────────────────────────
    if llm_api_url:
        from app.ingestion.llm_parser import parse_with_llm
        log.info(
            "llm_parser_used bank=%s model=%s text_fp=%s",
            bank_name,
            llm_model,
            text_fp,
        )
        llm_data, llm_err = parse_with_llm(
            text=text,
            api_url=llm_api_url,
            model=llm_model,
            api_key=llm_api_key,
            timeout_seconds=llm_timeout_seconds,
            text_fp=text_fp,
        )
        if llm_data is not None:
            result = _llm_result_to_parsed_statement(llm_data)
            prev_bank = result.bank_name
            result.bank_name = _reconcile_llm_bank_name(result.bank_name, text, bank_name)
            if (
                prev_bank
                and result.bank_name != prev_bank
                and (prev_bank.lower() in _FINTECH_FALSE_BANKS)
            ):
                result.parse_notes.append("bank_reconciled_fintech_trap")
            # Fill bank_name from detected value if LLM didn't provide it
            if not result.bank_name and bank_name:
                result.bank_name = bank_name
            # Try to extract card number from text if LLM missed it
            if not result.card_number:
                result.card_number = _extract_card_number(text)
            log.info(
                "llm_parse_ok bank=%s tx=%d text_fp=%s notes=%s",
                result.bank_name,
                len(result.transactions),
                text_fp,
                result.parse_notes,
            )
            log.info(
                "parser_parse_done path=llm bank=%s tx=%d notes=%s text_fp=%s",
                result.bank_name,
                len(result.transactions),
                result.parse_notes,
                text_fp,
            )
            _attach_statement_reminders(result, text)
            return result

        # LLM was configured but call failed (timeout, HTTP, invalid JSON, …)
        log.warning(
            "llm_unavailable_or_failed bank=%s err=%s text_fp=%s — empty statement",
            bank_name,
            llm_err,
            text_fp,
        )
        fallback = ParsedStatement()
        fallback.bank_name = bank_name or "Bilinmeyen Banka"
        fallback.card_number = _extract_card_number(text)
        if llm_err == "timeout":
            fallback.parse_notes = ["llm_timeout", "no_transactions_found"]
        else:
            fallback.parse_notes = ["llm_failed", "no_transactions_found"]
        log.info(
            "parser_parse_done path=llm_failed bank=%s tx=0 notes=%s text_fp=%s",
            fallback.bank_name,
            fallback.parse_notes,
            text_fp,
        )
        _attach_statement_reminders(fallback, text)
        return fallback

    # ── No LLM URL (disabled / not configured) ───────────────────────────────
    log.warning(
        "llm_not_configured bank=%s text_fp=%s — returning empty statement",
        bank_name,
        text_fp,
    )
    fallback = ParsedStatement()
    fallback.bank_name = bank_name or "Bilinmeyen Banka"
    fallback.card_number = _extract_card_number(text)
    fallback.parse_notes = ["no_llm_configured", "no_transactions_found"]
    log.info(
        "parser_parse_done path=no_llm bank=%s tx=0 notes=%s text_fp=%s",
        fallback.bank_name,
        fallback.parse_notes,
        text_fp,
    )
    _attach_statement_reminders(fallback, text)
    return fallback

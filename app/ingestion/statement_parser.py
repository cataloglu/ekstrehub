"""Statement parser — learned regex first (per bank), then LLM.

If a bank has stored regex rules from a prior successful LLM parse, those run locally (no API).
Otherwise PDF text goes to the configured LLM. A minimal fallback is used if LLM is unreachable.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

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


# ── Bank detection (for logging/context only, no parsing rules) ───────────────

_BANK_KEYWORDS: list[tuple[str, str]] = [
    ("denizbank", "DenizBank"),
    ("garanti", "Garanti BBVA"),
    ("yapı kredi", "Yapi Kredi"),
    ("yapikredi", "Yapi Kredi"),
    ("ykb", "Yapi Kredi"),
    ("akbank", "Akbank"),
    ("ziraat", "Ziraat Bankası"),
    ("vakıfbank", "VakıfBank"),
    ("vakifbank", "VakıfBank"),
    ("halkbank", "Halkbank"),
    ("iş bankası", "İş Bankası"),
    ("isbank", "İş Bankası"),
    ("işbank", "İş Bankası"),
    ("türkiye iş", "İş Bankası"),
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
        if keyword in lower:
            return name
    return None


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
    ps.bank_name = data.get("bank_name") or None
    ps.card_number = data.get("card_number") or None
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
    llm_timeout_seconds: int = 60,
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
    # Auto-detect bank from PDF text if not identified from email
    if not bank_name or bank_name.lower() in ("unknown", ""):
        bank_name = _detect_bank_from_text(text)

    if bank_name:
        log.info("bank_identified bank=%s", bank_name)

    # ── Learned local rules (no API) ───────────────────────────────────────────
    if learned_rules and not skip_learned_rules:
        from app.ingestion.learned_rules import try_apply_learned_rules

        local = try_apply_learned_rules(text, learned_rules, bank_name)
        if local and len(local.transactions) >= 1:
            log.info(
                "learned_local_parse_ok bank=%s tx=%d",
                bank_name,
                len(local.transactions),
            )
            return local

    # ── LLM parsing ───────────────────────────────────────────────────────────
    if llm_api_url:
        from app.ingestion.llm_parser import parse_with_llm
        log.info("llm_parser_used bank=%s model=%s", bank_name, llm_model)
        llm_data = parse_with_llm(
            text=text,
            api_url=llm_api_url,
            model=llm_model,
            api_key=llm_api_key,
            timeout_seconds=llm_timeout_seconds,
        )
        if llm_data is not None:
            result = _llm_result_to_parsed_statement(llm_data)
            # Fill bank_name from detected value if LLM didn't provide it
            if not result.bank_name and bank_name:
                result.bank_name = bank_name
            # Try to extract card number from text if LLM missed it
            if not result.card_number:
                result.card_number = _extract_card_number(text)
            log.info(
                "llm_parse_ok bank=%s tx=%d",
                result.bank_name,
                len(result.transactions),
            )
            return result

    # ── Fallback: LLM unavailable / failed ───────────────────────────────────
    log.warning("llm_unavailable_or_failed bank=%s — returning empty statement", bank_name)
    fallback = ParsedStatement()
    fallback.bank_name = bank_name or "Bilinmeyen Banka"
    fallback.card_number = _extract_card_number(text)
    fallback.parse_notes = ["llm_required", "no_transactions_found"]
    return fallback

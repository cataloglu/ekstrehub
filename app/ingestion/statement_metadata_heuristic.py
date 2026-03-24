"""Best-effort extraction of period / due / totals from Turkish PDF text when LLM is not used."""
from __future__ import annotations

import re
from datetime import date
from typing import Any

_DATE_DMY = re.compile(r"(\d{1,2})[./](\d{1,2})[./](\d{4})")
_PERIOD_RANGE = re.compile(
    r"(\d{1,2})[./](\d{1,2})[./](\d{4})\s*[-–/]\s*(\d{1,2})[./](\d{1,2})[./](\d{4})",
)
# Son ödeme ... 15.03.2026
_DUE_NEAR = re.compile(
    r"(?:son\s*ödeme|SON\s*ÖDEME|son\s*odeme)[^\d\n]{0,55}(\d{1,2})[./](\d{1,2})[./](\d{4})",
    re.IGNORECASE,
)
# TRY amounts 1.234,56 or 1234,56
_AMT_TRY = re.compile(
    r"(?:toplam|TOPLAM|ekstre\s*borc|borç|BORÇ)[^\d\n]{0,40}([\d]{1,3}(?:\.\d{3})*,\d{2})\s*(?:TL|TRY)?",
    re.IGNORECASE,
)
_MIN_PAY = re.compile(
    r"(?:asgari|ASGARI|minimum|MINIMUM)[^\d\n]{0,40}([\d]{1,3}(?:\.\d{3})*,\d{2})\s*(?:TL|TRY)?",
    re.IGNORECASE,
)


def _dmy(m: re.Match, g: int) -> date | None:
    d, mo, y = int(m.group(g)), int(m.group(g + 1)), int(m.group(g + 2))
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def _parse_tr_amount(s: str) -> float | None:
    s = s.strip().replace(" ", "")
    if not s:
        return None
    try:
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            parts = s.split(",")
            if len(parts[-1]) == 2 and parts[-1].isdigit():
                s = "".join(parts[:-1]) + "." + parts[-1]
            else:
                s = s.replace(",", ".")
        return float(s)
    except ValueError:
        return None


def enrich_parsed_statement_metadata(ps: Any, text: str) -> None:
    """Mutate *ps* with header fields found in raw PDF text (no LLM)."""
    if not text:
        return
    sample = text[:25_000]

    if ps.due_date is None:
        m = _DUE_NEAR.search(sample)
        if m:
            ps.due_date = _dmy(m, 1)

    if ps.statement_period_start is None and ps.statement_period_end is None:
        m = _PERIOD_RANGE.search(sample)
        if m:
            ps.statement_period_start = _dmy(m, 1)
            ps.statement_period_end = _dmy(m, 4)
        else:
            # Single "hesap kesim" style date as period_end
            for label in (
                r"(?:hesap\s*kesim|HESAP\s*KESİM|özet\s*tarihi|OZET\s*TARIHI|dönem\s*bitiş)",
            ):
                rx = re.compile(label + r"[^\d\n]{0,40}(\d{1,2})[./](\d{1,2})[./](\d{4})", re.I)
                m2 = rx.search(sample)
                if m2:
                    ps.statement_period_end = _dmy(m2, 1)
                    break

    if ps.total_due_try is None:
        m = _AMT_TRY.search(sample)
        if m:
            ps.total_due_try = _parse_tr_amount(m.group(1))

    if ps.minimum_due_try is None:
        m = _MIN_PAY.search(sample)
        if m:
            ps.minimum_due_try = _parse_tr_amount(m.group(1))

    filled = any(
        [
            ps.statement_period_end,
            ps.due_date,
            ps.total_due_try is not None,
        ]
    )
    if filled and "metadata_heuristic" not in (ps.parse_notes or []):
        ps.parse_notes = list(ps.parse_notes or [])
        ps.parse_notes.append("metadata_heuristic")

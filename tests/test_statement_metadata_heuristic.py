"""Heuristic header extraction for statements without full LLM parse."""
from __future__ import annotations

from datetime import date

from app.ingestion.statement_metadata_heuristic import enrich_parsed_statement_metadata
from app.ingestion.statement_parser import ParsedStatement


def test_enrich_finds_due_and_period_range() -> None:
    ps = ParsedStatement()
    text = """
    Türkiye İş Bankası
    Dönem 01.01.2026 - 24.02.2026
    Son Ödeme Tarihi 15.03.2026
    Toplam Borç 12.345,67 TL
    """
    enrich_parsed_statement_metadata(ps, text)
    assert ps.statement_period_start == date(2026, 1, 1)
    assert ps.statement_period_end == date(2026, 2, 24)
    assert ps.due_date == date(2026, 3, 15)
    assert ps.total_due_try == 12345.67

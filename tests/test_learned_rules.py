"""Tests for learned local regex rules."""
from app.ingestion.learned_rules import try_apply_learned_rules


def test_try_apply_simple_line_regex():
    rules = {
        "version": 1,
        "transaction_line_regex": r"(?P<date>\d{2}\.\d{2}\.\d{4})\s+(?P<description>.+?)\s+(?P<amount>[\d\.,]+)\s*TRY",
        "regex_flags": ["IGNORECASE"],
        "date_format": "%d.%m.%Y",
        "match_mode": "line",
    }
    text = """
    HESAP ÖZETİ
    15.01.2025  MARKET ABC  125,50 TRY
    16.01.2025  FUEL XYZ    1.234,56 TRY
    """
    ps = try_apply_learned_rules(text, rules, "TestBank")
    assert ps is not None
    assert len(ps.transactions) >= 1
    assert ps.bank_name == "TestBank"
    assert "learned_local_rules" in ps.parse_notes

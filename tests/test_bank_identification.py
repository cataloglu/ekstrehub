"""Bank name normalization and LLM merge behavior (regression for UI \"null\" bank)."""
from __future__ import annotations

import pytest

from app.ingestion.bank_identification import (
    canonical_bank_name,
    coalesce_bank_display,
    learned_rule_bank_keys,
    normalize_bank_name,
    normalize_optional_llm_str,
)
from app.ingestion.statement_parser import _llm_result_to_parsed_statement, parse_statement


def test_normalize_rejects_llm_null_string() -> None:
    assert normalize_bank_name("null") is None
    assert normalize_bank_name("NULL") is None
    assert normalize_bank_name(" none ") is None
    assert normalize_bank_name("bilinmeyen") is None


def test_normalize_keeps_real_names() -> None:
    assert normalize_bank_name("  DenizBank  ") == "DenizBank"
    assert normalize_bank_name("İş Bankası") == "İş Bankası"


def test_coalesce_bank_display_fixes_stored_null_string() -> None:
    assert coalesce_bank_display("null") is None
    assert coalesce_bank_display("Is Bankasi") == "İş Bankası"


def test_canonical_maps_legacy_profile_names() -> None:
    assert canonical_bank_name("Is Bankasi") == "İş Bankası"
    assert canonical_bank_name("Yapi Kredi") == "Yapı Kredi"
    assert canonical_bank_name("DenizBank") == "DenizBank"


def test_learned_rule_keys_include_legacy() -> None:
    keys = learned_rule_bank_keys("İş Bankası")
    assert "İş Bankası" in keys
    assert "Is Bankasi" in keys


def test_llm_result_drops_string_null_bank() -> None:
    data = {
        "bank_name": "null",
        "card_number": "null",
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "transactions": [
            {"date": "2026-01-01", "description": "x", "amount": 1.0, "currency": "TRY"},
        ],
    }
    ps = _llm_result_to_parsed_statement(data)
    assert ps.bank_name is None
    assert ps.card_number is None


def test_normalize_optional_llm_str_card() -> None:
    assert normalize_optional_llm_str("4548 12** **** 3456") == "4548 12** **** 3456"
    assert normalize_optional_llm_str("null") is None


def test_parse_statement_fills_bank_when_llm_emits_null_string(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ingestion import statement_parser as sp

    def fake_parse_with_llm(
        text: str,
        api_url: str,
        model: str,
        api_key: str = "",
        timeout_seconds: int = 120,
        *,
        text_fp: str | None = None,
    ):
        return (
            {
                "bank_name": "null",
                "transactions": [
                    {"date": "2026-01-01", "description": "x", "amount": 1.0, "currency": "TRY"},
                ],
            },
            None,
        )

    # Local import inside parse_statement resolves from llm_parser module
    monkeypatch.setattr("app.ingestion.llm_parser.parse_with_llm", fake_parse_with_llm)

    r = sp.parse_statement(
        "x",
        "İş Bankası",
        llm_api_url="http://localhost:11434/v1",
        llm_model="m",
        llm_api_key="",
    )
    assert r.bank_name == "İş Bankası"
    assert len(r.transactions) == 1

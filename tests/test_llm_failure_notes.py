"""Parse notes for LLM failure vs no-LLM configuration."""
from app.ingestion.statement_parser import ParsedStatement, is_llm_failure_empty


def test_is_llm_failure_empty_true_for_timeout():
    ps = ParsedStatement()
    ps.parse_notes = ["llm_timeout", "no_transactions_found"]
    assert is_llm_failure_empty(ps) is True


def test_is_llm_failure_empty_true_for_failed():
    ps = ParsedStatement()
    ps.parse_notes = ["llm_failed", "no_transactions_found"]
    assert is_llm_failure_empty(ps) is True


def test_is_llm_failure_empty_false_when_no_llm_config():
    ps = ParsedStatement()
    ps.parse_notes = ["no_llm_configured", "no_transactions_found"]
    assert is_llm_failure_empty(ps) is False


def test_is_llm_failure_empty_false_when_transactions():
    ps = ParsedStatement()
    ps.parse_notes = ["llm_timeout", "no_transactions_found"]
    from app.ingestion.statement_parser import ParsedTransaction
    from datetime import date

    ps.transactions.append(ParsedTransaction(date=date(2025, 1, 1), amount=1.0))
    assert is_llm_failure_empty(ps) is False

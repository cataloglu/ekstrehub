"""LLM sometimes returns Param/Papara as bank_name on real bank PDFs — reconcile with hint/text."""
from app.ingestion.reparse_from_imap import _coalesce_reparse_bank_hint
from app.ingestion.statement_parser import _reconcile_llm_bank_name, resolve_bank_hint


def test_param_overridden_when_email_hint_is_isbank() -> None:
    assert _reconcile_llm_bank_name("Param", "irrelevant body", "İş Bankası") == "İş Bankası"


def test_param_overridden_when_pdf_has_isbank_header() -> None:
    # ASCII-friendly: PDF text often contains "isbank" / ISBANK (encoding-safe in tests).
    text = "ISBANK A.S. Kredi Karti Ekstresi Maximiles"
    assert _reconcile_llm_bank_name("Param", text, None) == "İş Bankası"


def test_param_kept_when_only_param_wallet_context() -> None:
    text = "param cüzdan yukleme"
    assert _reconcile_llm_bank_name("Param", text, None) == "Param"


def test_garanti_not_replaced_by_param_llm_when_garanti_in_text() -> None:
    text = "Garanti BBVA kredi karti ekstresi"
    assert _reconcile_llm_bank_name("Param", text, None) == "Garanti BBVA"


def test_resolve_bank_hint_drops_param_and_uses_pdf() -> None:
    text = "ISBANK A.S. Kredi Karti Ekstresi Maximiles"
    assert resolve_bank_hint("Param", text) == "İş Bankası"


def test_coalesce_reparse_prefers_email_when_json_is_param() -> None:
    assert _coalesce_reparse_bank_hint("Param", "İş Bankası") == "İş Bankası"


def test_coalesce_reparse_keeps_good_json_over_email() -> None:
    assert _coalesce_reparse_bank_hint("Garanti BBVA", "İş Bankası") == "Garanti BBVA"

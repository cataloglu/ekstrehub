"""Regression: bank detection from PDF text must not confuse substrings."""
from app.ingestion.statement_parser import _detect_bank_from_text


def test_param_not_detected_inside_parametre() -> None:
    assert _detect_bank_from_text("Bu parametre değeri geçerlidir.") is None


def test_param_wallet_still_detected_as_standalone_word() -> None:
    # Whole-word "param" (e.g. merchant line) still maps — rare bank/wallet label
    assert _detect_bank_from_text("param cüzdan yüklemesi") is not None

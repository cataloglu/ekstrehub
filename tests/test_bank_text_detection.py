"""Regression: bank detection from PDF text must not confuse substrings."""
from app.ingestion.statement_parser import _detect_bank_from_text


def test_param_not_detected_inside_parametre() -> None:
    assert _detect_bank_from_text("Bu parametre değeri geçerlidir.") is None


def test_param_wallet_still_detected_as_standalone_word() -> None:
    # Whole-word "param" (e.g. merchant line) still maps — rare bank/wallet label
    assert _detect_bank_from_text("param cüzdan yüklemesi") is not None


def test_isbank_maximiles_prefers_over_param_pos_line() -> None:
    """İş Maximiles Black: POS satırı PARAM/... geçse bile ürün sütunları İş’i gösterir."""
    text = (
        "KREDİ KARTI HESAP ÖZETİ\n"
        "MAXIMILES BLACK\n"
        "30/11/2025 PARAM/GETIR ISTANBUL TR 736,22\n"
        "maximiles.com.tr 0850 724 0 724"
    )
    assert _detect_bank_from_text(text) == "İş Bankası"


def test_isbank_maximil_column_without_full_maximiles_word() -> None:
    """Bazı PDF çıktılarında sütun adı MAXIMIL olarak gelir (MAXIMILES tam yazılmaz)."""
    text = "İŞLEM TARİHİ AÇIKLAMA MAXIMIL MAXIPUAN\nPARAM/GETIR ISTANBUL"
    assert _detect_bank_from_text(text) == "İş Bankası"

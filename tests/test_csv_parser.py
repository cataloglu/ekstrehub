from decimal import Decimal

from app.ingestion.csv_parser import parse_statement_csv


def test_parse_csv_with_turkish_columns_and_amount() -> None:
    # RFC-compliant CSV uses comma separators; Turkish decimal comma is quoted.
    raw = (
        "Islem Tarihi,Aciklama,Tutar,Para_Birimi\n"
        '21.02.2026,"Market Alisverisi","1.234,56",TRY\n'
    ).encode("utf-8")

    rows = parse_statement_csv(raw)
    assert len(rows) == 1
    assert rows[0].description == "Market Alisverisi"
    assert rows[0].amount == Decimal("1234.56")
    assert rows[0].currency == "TRY"


def test_parse_csv_with_english_columns() -> None:
    raw = (
        "TransactionDate,Description,Amount,Currency\n"
        "2026-02-20T10:30:00,Coffee,-45.90,TRY\n"
    ).encode("utf-8")

    rows = parse_statement_csv(raw)
    assert len(rows) == 1
    assert rows[0].description == "Coffee"
    assert rows[0].amount == Decimal("-45.90")
    assert rows[0].currency == "TRY"
    assert rows[0].original_currency is None


def test_parse_csv_foreign_currency_normalized_to_try() -> None:
    raw = (
        "TransactionDate,Description,Amount,Currency\n"
        "2026-02-20,Online Subscription,12.99,USD\n"
    ).encode("utf-8")

    rows = parse_statement_csv(raw)
    assert len(rows) == 1
    assert rows[0].currency == "TRY"
    assert rows[0].original_currency == "USD"

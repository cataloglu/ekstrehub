from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from io import StringIO


@dataclass(frozen=True)
class CsvTransaction:
    tx_date: date
    description: str
    amount: Decimal
    currency: str
    original_currency: str | None


def parse_statement_csv(raw_content: bytes) -> list[CsvTransaction]:
    text = raw_content.decode("utf-8-sig", errors="ignore")
    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames:
        return []

    mapping = _resolve_column_mapping(reader.fieldnames)
    transactions: list[CsvTransaction] = []

    for row in reader:
        date_value = _parse_date((row.get(mapping["date"]) or "").strip())
        amount_value = _parse_amount((row.get(mapping["amount"]) or "").strip())
        description = (row.get(mapping["description"]) or "").strip()
        source_currency = (row.get(mapping["currency"]) or "TRY").strip().upper() or "TRY"
        normalized_currency = "TRY"

        if not description:
            description = "UNKNOWN"

        transactions.append(
            CsvTransaction(
                tx_date=date_value,
                description=description,
                amount=amount_value,
                currency=normalized_currency,
                original_currency=source_currency if source_currency != "TRY" else None,
            )
        )

    return transactions


def _resolve_column_mapping(fieldnames: list[str]) -> dict[str, str]:
    normalized = {name.strip().lower(): name for name in fieldnames}

    date_col = _pick_column(
        normalized,
        ["transactiondate", "date", "islemtarihi", "islem_tarihi", "islem tarihi"],
    )
    amount_col = _pick_column(normalized, ["amount", "tutar", "islemtutari", "islem_tutari"])
    description_col = _pick_column(normalized, ["description", "aciklama", "islemaciklama", "islem_aciklama"])
    currency_col = _pick_column(normalized, ["currency", "doviz", "para_birimi", "parabirimi"], optional=True)

    return {
        "date": date_col,
        "amount": amount_col,
        "description": description_col,
        "currency": currency_col or "",
    }


def _pick_column(normalized: dict[str, str], candidates: list[str], optional: bool = False) -> str:
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    if optional:
        return ""
    raise ValueError(f"Missing required CSV column. Tried: {', '.join(candidates)}")


def _parse_date(raw: str) -> date:
    if not raw:
        raise ValueError("Date value cannot be empty.")

    formats = ("%d.%m.%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y")
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {raw}")


def _parse_amount(raw: str) -> Decimal:
    if not raw:
        raise ValueError("Amount value cannot be empty.")

    sanitized = raw.replace(" ", "")
    if "," in sanitized and "." in sanitized:
        sanitized = sanitized.replace(".", "").replace(",", ".")
    elif "," in sanitized:
        sanitized = sanitized.replace(",", ".")

    return Decimal(sanitized)

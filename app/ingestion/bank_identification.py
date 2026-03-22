"""Bank name normalization — single place for hints (email/PDF) + LLM output.

LLMs often emit the *string* \"null\" for bank_name; that is truthy in Python and
blocked merging with email/PDF hints. We treat those as missing and fall back to
detection hints. Legacy profile spellings are mapped to canonical Turkish names.
"""
from __future__ import annotations

from typing import Any

# Values that must never be stored as a bank display name (case-insensitive).
_INVALID_BANK_LITERALS: frozenset[str] = frozenset(
    {
        "",
        "null",
        "none",
        "undefined",
        "n/a",
        "na",
        "-",
        "--",
        "—",
        "unknown",
        "bilinmeyen",
        "bilinmeyen banka",
        "yok",
        "?",
    }
)

# Exact legacy DB / profile strings → canonical display name (UI + new rows).
_LEGACY_TO_CANONICAL: dict[str, str] = {
    "Is Bankasi": "İş Bankası",
    "Yapi Kredi": "Yapı Kredi",
}


def normalize_bank_name(value: str | None) -> str | None:
    """Return a clean bank name, or None if the value is missing/placeholder."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    low = s.lower()
    if low in _INVALID_BANK_LITERALS:
        return None
    return s


def canonical_bank_name(value: str | None) -> str | None:
    """Map legacy spellings (e.g. email profile) to one canonical Turkish name."""
    n = normalize_bank_name(value)
    if not n:
        return None
    return _LEGACY_TO_CANONICAL.get(n, n)


def normalize_optional_llm_str(value: Any) -> str | None:
    """For card_number and similar: LLM string \"null\" → None."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    low = s.lower()
    if low in _INVALID_BANK_LITERALS:
        return None
    return s


def coalesce_bank_display(stored: str | None) -> str | None:
    """API/UI: normalize legacy DB values (string \"null\", old profile spellings)."""
    return canonical_bank_name(normalize_bank_name(stored))


def learned_rule_bank_keys(bank_name: str | None) -> list[str]:
    """DB lookup order for learned_parser_rules (handles legacy row keys)."""
    if not bank_name:
        return []
    b = bank_name.strip()
    keys: list[str] = []
    canon = canonical_bank_name(b) or b
    for k in (b, canon):
        if k and k not in keys:
            keys.append(k)
    # Legacy keys stored before canonicalization
    if canon == "İş Bankası" and "Is Bankasi" not in keys:
        keys.append("Is Bankasi")
    if canon == "Yapı Kredi" and "Yapi Kredi" not in keys:
        keys.append("Yapi Kredi")
    return keys

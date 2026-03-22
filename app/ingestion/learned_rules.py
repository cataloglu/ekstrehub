"""Learned local parsers: after a successful LLM parse, we store a regex JSON per bank.

Next PDFs for the same bank try local regex first — no API call. If matches fail, fall back to LLM.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import LearnedParserRule
from app.ingestion.bank_identification import (
    canonical_bank_name,
    learned_rule_bank_keys,
    normalize_bank_name,
)
from app.ingestion.statement_parser import ParsedStatement, ParsedTransaction

log = logging.getLogger(__name__)

_RULE_VERSION = 1


def fingerprint_text_sample(text: str) -> str:
    """Rough layout fingerprint (digits normalized) for logging."""
    sample = text[:4000]
    normalized = re.sub(r"\d", "0", sample)
    return hashlib.sha256(normalized.encode("utf-8", errors="ignore")).hexdigest()[:32]


def load_learned_rule_dict(session: Session, bank_name: str | None) -> dict[str, Any] | None:
    bn = canonical_bank_name(normalize_bank_name(bank_name))
    if not bn or bn.lower() in ("bilinmeyen banka",):
        return None
    for key in learned_rule_bank_keys(bn):
        row = session.scalar(select(LearnedParserRule).where(LearnedParserRule.bank_name == key))
        if row:
            try:
                return json.loads(row.rules_json)
            except Exception:
                return None
    return None


def upsert_learned_rule(session: Session, bank_name: str, rules: dict[str, Any], fingerprint: str | None) -> None:
    bank_name = canonical_bank_name(normalize_bank_name(bank_name)) or bank_name
    js = json.dumps(rules, ensure_ascii=False)
    existing = session.scalar(select(LearnedParserRule).where(LearnedParserRule.bank_name == bank_name))
    if existing:
        existing.rules_json = js
        existing.source_fingerprint = fingerprint
    else:
        session.add(
            LearnedParserRule(
                bank_name=bank_name,
                rules_json=js,
                source_fingerprint=fingerprint,
            )
        )
    session.flush()


def _parse_tr_amount(s: str) -> float | None:
    s = (s or "").strip().replace(" ", "").replace("TRY", "").replace("TL", "")
    if not s:
        return None
    try:
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            parts = s.split(",")
            if len(parts[-1]) == 2 and parts[-1].isdigit():
                s = "".join(parts[:-1]) + "." + parts[-1]
            else:
                s = s.replace(",", ".")
        return float(s)
    except ValueError:
        return None


def _parse_date_flexible(raw: str, primary_fmt: str) -> Any:
    raw = (raw or "").strip()[:16]
    if not raw:
        return None
    fmts = [primary_fmt, "%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]
    seen: set[str] = set()
    for f in fmts:
        if f in seen:
            continue
        seen.add(f)
        try:
            return datetime.strptime(raw[:10], f).date()
        except ValueError:
            continue
    return None


def _group_get(groupdict: dict[str, str], *names: str) -> str:
    for k, v in groupdict.items():
        if k and v is not None and k.lower() in {n.lower() for n in names}:
            return str(v).strip()
    for name in names:
        if name in groupdict and groupdict[name]:
            return str(groupdict[name]).strip()
    return ""


def try_apply_learned_rules(
    text: str,
    rules: dict[str, Any],
    bank_name: str | None,
    *,
    text_fp: str | None = None,
) -> ParsedStatement | None:
    """Apply stored regex rules. Returns None if unusable or no matches."""
    fp = text_fp or "-"
    if not rules or rules.get("version") != _RULE_VERSION:
        log.info(
            "learned_skip reason=bad_version_or_empty bank=%s version=%s text_fp=%s",
            bank_name,
            (rules or {}).get("version"),
            fp,
        )
        return None
    pattern = (rules.get("transaction_line_regex") or "").strip()
    if not pattern:
        log.info("learned_skip reason=no_pattern bank=%s text_fp=%s", bank_name, fp)
        return None
    flags = 0
    for f in rules.get("regex_flags") or []:
        if f == "IGNORECASE":
            flags |= re.IGNORECASE
        if f == "MULTILINE":
            flags |= re.MULTILINE
    try:
        rx = re.compile(pattern, flags)
    except re.error as exc:
        log.warning(
            "learned_skip reason=regex_compile bank=%s err=%s pattern_preview=%s text_fp=%s",
            bank_name,
            exc,
            pattern[:120].replace("\n", " "),
            fp,
        )
        return None

    date_fmt = rules.get("date_format") or "%d.%m.%Y"
    match_mode = rules.get("match_mode") or "line"
    txs: list[ParsedTransaction] = []
    regex_hits = 0
    amount_parse_failed = 0
    if match_mode == "line":
        for line in text.splitlines():
            line = line.strip()
            if len(line) < 10:
                continue
            m = rx.search(line)
            if not m:
                continue
            regex_hits += 1
            gd = m.groupdict()
            d_raw = _group_get(gd, "date", "tarih")
            desc = _group_get(gd, "description", "desc", "aciklama")
            amt_raw = _group_get(gd, "amount", "tutar")
            d = _parse_date_flexible(d_raw, date_fmt)
            amt = _parse_tr_amount(amt_raw)
            if amt is None:
                amount_parse_failed += 1
                continue
            txs.append(
                ParsedTransaction(
                    date=d,
                    description=desc or "",
                    amount=amt,
                    currency="TRY",
                )
            )
    else:
        for m in rx.finditer(text):
            regex_hits += 1
            gd = m.groupdict()
            d_raw = _group_get(gd, "date", "tarih")
            desc = _group_get(gd, "description", "desc", "aciklama")
            amt_raw = _group_get(gd, "amount", "tutar")
            d = _parse_date_flexible(d_raw, date_fmt)
            amt = _parse_tr_amount(amt_raw)
            if amt is None:
                amount_parse_failed += 1
                continue
            txs.append(
                ParsedTransaction(
                    date=d,
                    description=desc or "",
                    amount=amt,
                    currency="TRY",
                )
            )

    if len(txs) < 1:
        log.info(
            "learned_skip reason=no_valid_transactions bank=%s mode=%s regex_hits=%d "
            "amount_parse_failed=%d text_fp=%s",
            bank_name,
            match_mode,
            regex_hits,
            amount_parse_failed,
            fp,
        )
        return None

    ps = ParsedStatement()
    ps.bank_name = bank_name
    ps.transactions = txs
    ps.parse_notes = ["learned_local_rules"]
    ps.card_number = None
    return ps


def _count_rule_matches(text: str, rules: dict[str, Any]) -> int:
    pattern = (rules.get("transaction_line_regex") or "").strip()
    if not pattern:
        return 0
    flags = 0
    for f in rules.get("regex_flags") or []:
        if f == "IGNORECASE":
            flags |= re.IGNORECASE
        if f == "MULTILINE":
            flags |= re.MULTILINE
    try:
        rx = re.compile(pattern, flags)
    except re.error:
        return 0
    if (rules.get("match_mode") or "line") == "line":
        return sum(1 for line in text.splitlines() if line.strip() and rx.search(line.strip()))
    return len(rx.findall(text))


def generate_rules_via_llm(
    text: str,
    parsed: ParsedStatement,
    api_url: str,
    model: str,
    api_key: str,
    timeout_seconds: int,
) -> dict[str, Any] | None:
    """Ask LLM to emit regex JSON; validate by counting line matches."""
    sample = [
        {"date": str(tx.date) if tx.date else None, "description": (tx.description or "")[:100], "amount": tx.amount}
        for tx in parsed.transactions[:25]
    ]
    excerpt = text[:8000]
    system = (
        "You output ONLY one JSON object, no markdown. Keys:\n"
        '{"version":1,"transaction_line_regex":"...","regex_flags":["IGNORECASE"],"date_format":"%d.%m.%Y","match_mode":"line"}\n'
        "The regex MUST use Python named groups: date, description, amount.\n"
        "It must match one full line of a Turkish credit card statement (date, text, TRY amount).\n"
        "Amount may look like 1.234,56 or 12,34 TRY."
    )
    user = (
        "Successful reference transactions (JSON):\n"
        f"{json.dumps(sample, ensure_ascii=False)}\n\n"
        "Raw statement excerpt:\n---\n"
        f"{excerpt}\n---\n"
        "Produce regex that matches similar lines in this bank format."
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.0,
        "max_tokens": 1800,
    }
    endpoint = api_url.rstrip("/") + "/chat/completions"
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.URLError as exc:
        log.warning("learn_rules_llm_unreachable %s", exc)
        return None
    try:
        data = json.loads(raw)
        content = data["choices"][0]["message"]["content"]
        content = content.strip()
        content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.MULTILINE)
        content = re.sub(r"\s*```$", "", content, flags=re.MULTILINE)
        rules = json.loads(content)
    except Exception as exc:
        log.warning("learn_rules_llm_bad_json %s", exc)
        return None

    if rules.get("version") != _RULE_VERSION:
        rules["version"] = _RULE_VERSION
    rules.setdefault("regex_flags", ["IGNORECASE"])
    rules.setdefault("date_format", "%d.%m.%Y")
    rules.setdefault("match_mode", "line")

    cnt = _count_rule_matches(text, rules)
    ref_n = max(1, min(3, len(parsed.transactions)))
    if cnt < 1:
        log.warning("learn_rules_zero_matches got=%d need>=1", cnt)
        return None
    if cnt < ref_n:
        log.warning(
            "learn_rules_few_matches got=%d ideal>=%d saving_anyway",
            cnt,
            ref_n,
        )
    return rules


def maybe_train_learned_rules(
    session: Session,
    bank_name: str | None,
    text: str,
    parsed: ParsedStatement,
    llm: dict[str, Any],
) -> None:
    """After LLM parse: derive regex rules and store (no extra call if disabled)."""
    if os.getenv("EKSTREHUB_DISABLE_LEARN_RULES", "").strip() in ("1", "true", "yes"):
        return
    bn = canonical_bank_name(normalize_bank_name(bank_name))
    if not bn or bn.lower() in ("bilinmeyen banka",):
        return
    if "learned_local_rules" in (parsed.parse_notes or []):
        return
    if not parsed.transactions:
        return
    if not llm.get("llm_enabled") or not (llm.get("llm_api_url") or "").strip():
        return

    try:
        rules = generate_rules_via_llm(
            text,
            parsed,
            llm["llm_api_url"],
            llm["llm_model"],
            llm["llm_api_key"],
            int(llm.get("llm_timeout_seconds", 120)),
        )
    except Exception as exc:
        log.warning("learn_rules_failed %s", exc)
        return
    if not rules:
        return
    fp = fingerprint_text_sample(text)
    upsert_learned_rule(session, bn, rules, fp)
    log.info("learned_rules_saved bank=%s matches_in_text=%d", bn, _count_rule_matches(text, rules))

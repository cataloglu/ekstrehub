"""AI-powered statement parser using any OpenAI-compatible LLM API.

Works with:
- Ollama  (LLM_API_URL=http://localhost:11434/v1, LLM_MODEL=qwen2.5:7b)
- LM Studio (LLM_API_URL=http://localhost:1234/v1, LLM_MODEL=...)
- OpenAI  (LLM_API_URL=https://api.openai.com/v1, LLM_API_KEY=sk-..., LLM_MODEL=gpt-4o-mini)

Configure via environment variables (see config.py).
"""
from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from typing import Any

log = logging.getLogger(__name__)

# Maximum characters sent to the LLM.
# OpenAI gpt-4o-mini supports ~128k tokens; 24k chars ≈ 6k tokens — plenty for any statement.
_MAX_TEXT_CHARS = 24_000

_SYSTEM_PROMPT = """\
Sen bir Türk banka kredi kartı ekstresi ayrıştırıcısısın.
Sana herhangi bir Türk bankasından (DenizBank, İş Bankası, Garanti BBVA, Yapı Kredi, \
Akbank, Ziraat, Vakıfbank, Halkbank, QNB Finansbank, TEB, ING, HSBC vb.) \
PDF'den çıkarılmış ekstre metni verilecek.
Metni dikkatle okuyup aşağıdaki JSON formatında SADECE JSON döndür, başka hiçbir şey yazma.

{
  "bank_name": "Banka adı (örn: DenizBank, İş Bankası, Garanti BBVA, Yapı Kredi)",
  "card_number": "Kart numarası (örn: 4548 08** **** 1234 veya null)",
  "period_start": "YYYY-MM-DD veya null",
  "period_end": "YYYY-MM-DD veya null (hesap kesim tarihi)",
  "due_date": "YYYY-MM-DD veya null (son ödeme tarihi)",
  "total_due_try": 12345.67,
  "minimum_due_try": 1234.56,
  "transactions": [
    {
      "date": "YYYY-MM-DD",
      "description": "İşlem açıklaması",
      "amount": 123.45,
      "currency": "TRY"
    }
  ]
}

Kurallar:
- bank_name: Sadece ekstreyi düzenleyen banka (kartı veren kurum). **Asla** «Param» veya «Papara» yazma — bunlar POS/ödeme markasıdır, banka değildir (İş Bankası ekstresinde bile işlem satırında «Param» geçebilir). Üst bilgi bazen **yalnızca logo (görsel)** olduğundan metinde banka adı çıkmayabilir; o zaman ürün adından çıkar: **Maximiles / Maximum / MaxiPuan** → İş Bankası, **World** (kart) → Yapı Kredi, **Bonus** → Garanti BBVA vb. PDF metninde geçen resmi banka adını tercih et.
- TÜM işlemleri listele, hiçbirini atlama (ödemeler dahil)
- Ödemeler, iadeler, iptal ve düzeltmeler için amount negatif olmalı (örn: -1000.0)
- Alışveriş ve harcamalar için amount pozitif olmalı
- Türk para formatını ondalık sayıya çevir: 1.234,56 → 1234.56
- Tarihler her zaman YYYY-MM-DD formatında (gün/ay/yıl veya yıl-ay-gün olabilir, dönüştür)
- currency: TRY, USD, EUR, GBP gibi 3 harfli ISO kodu (belirtilmemişse TRY)
- Taksitli işlemlerde sadece bu döneme ait taksit tutarını yaz
- Faiz (FIZ), BSMV, KKDF, aidat satırlarını da işlem olarak ekle
- Kart numarasını gizlenmiş haliyle yaz (örn: 4548 08** **** 1234)
- Eğer bir alan bulunamıyorsa JSON null kullan (tırnaksız). bank_name ve card_number için \
asla "null", "none" veya "bilinmeyen" gibi metin yazma — bilinmiyorsa JSON null kullan.
- SADECE metinde **gerçekten var olan** işlemleri çıkar; uydurma, tahmine dayalı satır ekleme. \
Emin değilsen o satırı atla — eksik veri yanlış veriden iyidir.
- minimum_due_try asla total_due_try'dan büyük olamaz.
- period_start her zaman period_end'den önce (veya aynı) olmalıdır.
- SADECE JSON döndür, markdown code block kullanma, açıklama yazma"""

_USER_PROMPT_TEMPLATE = """\
Aşağıdaki banka ekstresi metnini ayrıştır ve tüm işlemleri çıkar:

---
{text}
---"""


def _truncate_text(text: str) -> str:
    if len(text) <= _MAX_TEXT_CHARS:
        return text
    # Page-aware split: try to cut at page boundaries (\f) to minimize mid-transaction loss.
    pages = text.split("\f")
    if len(pages) > 2:
        head_pages: list[str] = []
        tail_pages: list[str] = []
        head_len = 0
        head_budget = int(_MAX_TEXT_CHARS * 0.65)
        for p in pages:
            if head_len + len(p) < head_budget:
                head_pages.append(p)
                head_len += len(p)
            else:
                break
        tail_budget = _MAX_TEXT_CHARS - head_len - 100
        tail_len = 0
        for p in reversed(pages[len(head_pages):]):
            if tail_len + len(p) < tail_budget:
                tail_pages.insert(0, p)
                tail_len += len(p)
            else:
                break
        if head_pages and tail_pages:
            skipped = len(pages) - len(head_pages) - len(tail_pages)
            sep = f"\n...[{skipped} sayfa kısaltıldı]...\n" if skipped > 0 else "\n"
            return "\f".join(head_pages) + sep + "\f".join(tail_pages)
    # Fallback: character-based head+tail
    head = text[: int(_MAX_TEXT_CHARS * 0.65)]
    tail = text[-int(_MAX_TEXT_CHARS * 0.30):]
    return head + "\n...[metin kısaltıldı]...\n" + tail


def _extract_json_from_response(content: str) -> dict[str, Any]:
    """Extract JSON from LLM response, handling markdown code blocks and truncation."""
    content = content.strip()
    # Remove markdown code fences if present
    content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.MULTILINE)
    content = re.sub(r"\s*```$", "", content, flags=re.MULTILINE)
    content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Try to recover truncated JSON by closing open arrays/objects
        # Find the last complete transaction object and truncate there
        repaired = _repair_truncated_json(content)
        if repaired:
            return repaired
        raise


def _repair_truncated_json(content: str) -> dict[str, Any] | None:
    """Attempt to repair truncated JSON by brace-matching, not fixed whitespace."""
    # Strategy: find the last complete '}' that keeps valid JSON when we close arrays/objects.
    # Walk backwards through '}' positions and try closing the structure.
    brace_positions = [i for i, c in enumerate(content) if c == "}"]
    for pos in reversed(brace_positions):
        candidate = content[: pos + 1]
        # Count unclosed brackets
        opens = candidate.count("[") - candidate.count("]")
        open_braces = candidate.count("{") - candidate.count("}")
        suffix = "]" * max(opens, 0) + "}" * max(open_braces, 0)
        try:
            result = json.loads(candidate + suffix)
            if isinstance(result, dict) and "transactions" in result:
                n = len(result.get("transactions", []))
                log.warning("json_repaired_from_truncation transactions=%d", n)
                result.setdefault("parse_notes", [])
                result["parse_notes"].append("llm_output_truncated")
                return result
        except json.JSONDecodeError:
            continue
    return None


def call_llm(
    text: str,
    api_url: str,
    model: str,
    api_key: str = "",
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    """Send statement text to an OpenAI-compatible LLM and return parsed dict.

    Args:
        text:            Full extracted PDF text.
        api_url:         Base URL of the API (e.g. http://localhost:11434/v1).
        model:           Model name (e.g. qwen2.5:7b, gpt-4o-mini).
        api_key:         API key (empty for Ollama).
        timeout_seconds: Request timeout.

    Returns:
        Parsed dict with keys matching ParsedStatement fields.

    Raises:
        RuntimeError: If the LLM call fails or response is not valid JSON.
    """
    truncated = _truncate_text(text)
    log.info(
        "llm_call_start model=%s timeout=%ds text_len=%d truncated_len=%d",
        model,
        timeout_seconds,
        len(text),
        len(truncated),
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _USER_PROMPT_TEMPLATE.format(text=truncated)},
        ],
        "temperature": 0.0,
        "max_tokens": 16000,
        "stream": False,
    }

    endpoint = api_url.rstrip("/") + "/chat/completions"
    body = json.dumps(payload).encode("utf-8")
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"LLM API unreachable at {endpoint}: {exc}") from exc

    response_data = json.loads(raw)
    content = response_data["choices"][0]["message"]["content"]
    finish_reason = response_data["choices"][0].get("finish_reason", "?")
    log.info("llm_raw_response length=%d finish_reason=%s", len(content), finish_reason)
    # Also expose finish_reason for debugging
    if finish_reason == "length":
        log.warning("llm_output_truncated: increase max_tokens")

    try:
        return _extract_json_from_response(content)
    except (json.JSONDecodeError, KeyError) as exc:
        raise RuntimeError(f"LLM returned invalid JSON: {exc}\nContent: {content[:500]}") from exc


def parse_with_llm(
    text: str,
    api_url: str,
    model: str,
    api_key: str = "",
    timeout_seconds: int = 120,
    *,
    text_fp: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Try to parse statement with LLM.

    Returns (data, None) on success, or (None, reason) on failure.
    reason is \"timeout\" for read timeouts, \"failed\" for other errors.
    """
    fp = text_fp or "-"
    try:
        result = call_llm(text, api_url, model, api_key, timeout_seconds)
        n_tx = len(result.get("transactions", []))
        log.info(
            "llm_parse_ok model=%s bank=%s transactions=%d text_fp=%s",
            model,
            result.get("bank_name"),
            n_tx,
            fp,
        )
        if n_tx == 0:
            log.warning(
                "llm_returned_zero_transactions model=%s bank_in_json=%s text_fp=%s",
                model,
                result.get("bank_name"),
                fp,
            )
        return result, None
    except Exception as exc:
        log.warning("llm_parse_failed model=%s reason=%s text_fp=%s", model, exc, fp)
        err = str(exc).lower()
        if "timed out" in err or "timeout" in err:
            return None, "timeout"
        return None, "failed"

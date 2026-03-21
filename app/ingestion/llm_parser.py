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
- TÜM işlemleri listele, hiçbirini atlama (ödemeler dahil)
- Ödemeler, iadeler, iptal ve düzeltmeler için amount negatif olmalı (örn: -1000.0)
- Alışveriş ve harcamalar için amount pozitif olmalı
- Türk para formatını ondalık sayıya çevir: 1.234,56 → 1234.56
- Tarihler her zaman YYYY-MM-DD formatında (gün/ay/yıl veya yıl-ay-gün olabilir, dönüştür)
- currency: TRY, USD, EUR, GBP gibi 3 harfli ISO kodu (belirtilmemişse TRY)
- Taksitli işlemlerde sadece bu döneme ait taksit tutarını yaz
- Faiz (FIZ), BSMV, KKDF, aidat satırlarını da işlem olarak ekle
- Kart numarasını gizlenmiş haliyle yaz (örn: 4548 08** **** 1234)
- Eğer bir alan bulunamıyorsa null kullan
- SADECE JSON döndür, markdown code block kullanma, açıklama yazma"""

_USER_PROMPT_TEMPLATE = """\
Aşağıdaki banka ekstresi metnini ayrıştır ve tüm işlemleri çıkar:

---
{text}
---"""


def _truncate_text(text: str) -> str:
    if len(text) <= _MAX_TEXT_CHARS:
        return text
    # Keep first 2/3 (summary + first transactions) and last 1/3 (totals)
    head = text[: int(_MAX_TEXT_CHARS * 0.7)]
    tail = text[-int(_MAX_TEXT_CHARS * 0.3):]
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
    """Attempt to repair truncated JSON by closing incomplete structures."""
    # Find the last complete transaction (ends with "}" before any comma or bracket)
    tx_end = content.rfind('}\n    ]')
    if tx_end == -1:
        tx_end = content.rfind('}\n  ]')
    if tx_end == -1:
        # Try to find last complete tx by looking for last complete }
        # and close the array + object
        last_complete_tx = content.rfind('\n    }')
        if last_complete_tx == -1:
            return None
        truncated = content[:last_complete_tx + 6]  # include closing }
        repaired = truncated + "\n  ]\n}"
    else:
        repaired = content[:tx_end + 7] + "\n}"
    try:
        result = json.loads(repaired)
        log.warning("json_repaired_from_truncation transactions=%d", len(result.get("transactions", [])))
        result.setdefault("parse_notes", [])
        result["parse_notes"].append("llm_output_truncated")
        return result
    except json.JSONDecodeError:
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

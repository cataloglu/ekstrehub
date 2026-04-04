from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger("ekstrehub.ha_notifier")


def _enabled() -> bool:
    raw = (os.getenv("EKSTREHUB_HA_NOTIFY_ENABLED") or "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _ha_api_base() -> str:
    base = (os.getenv("HA_CORE_API_URL") or "http://supervisor/core/api").strip().rstrip("/")
    if not base.endswith("/api"):
        base = f"{base}/api"
    return base


def _supervisor_token() -> str:
    return (os.getenv("SUPERVISOR_TOKEN") or "").strip()


def _post_json(base: str, token: str, path: str, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{base}{path}",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status >= 400:
            raise RuntimeError(f"HA notify HTTP {resp.status}")


def notify_new_statements_to_ha(
    summary: dict[str, Any],
    *,
    account_label: str | None,
    imap_user: str | None,
    source: str,
) -> bool:
    """Send HA notifications/sensors when new statements are saved."""
    saved = int(summary.get("saved_documents") or 0)
    if saved <= 0:
        return False
    if not _enabled():
        return False

    token = _supervisor_token()
    if not token:
        log.info("ha_notify_skipped reason=no_supervisor_token saved=%d", saved)
        return False

    base = _ha_api_base()
    now_iso = datetime.now(timezone.utc).isoformat()
    scanned = int(summary.get("scanned_messages") or 0)
    processed = int(summary.get("processed_messages") or 0)
    duplicates = int(summary.get("duplicate_messages") or 0)
    failed = int(summary.get("failed_messages") or 0)
    run_id = summary.get("run_id")
    details_raw = summary.get("statement_details")
    statement_details = details_raw if isinstance(details_raw, list) else []
    account_text = " · ".join(x for x in [account_label, imap_user] if x) or "mail hesabı"

    title = "EkstreHub: Yeni ekstre bulundu"
    message = (
        f"{saved} yeni ekstre kaydedildi ({account_text}).\n"
        f"run#{run_id} · taranan {scanned} · işlenen {processed} · tekrar {duplicates} · hata {failed}"
    )
    state_attrs = {
        "run_id": run_id,
        "saved_documents": saved,
        "scanned_messages": scanned,
        "processed_messages": processed,
        "duplicate_messages": duplicates,
        "failed_messages": failed,
        "account_label": account_label,
        "imap_user": imap_user,
        "source": source,
        "updated_at": now_iso,
        "statement_details": statement_details,
    }
    if statement_details:
        first = statement_details[0] if isinstance(statement_details[0], dict) else {}
        state_attrs["latest_due_date"] = first.get("due_date")
        state_attrs["latest_total_debt"] = first.get("total_debt")

    try:
        _post_json(
            base,
            token,
            "/services/persistent_notification/create",
            {
                "title": title,
                "message": message,
                "notification_id": "ekstrehub_new_statement",
            },
        )
        _post_json(
            base,
            token,
            "/states/sensor.ekstrehub_new_statements",
            {
                "state": str(saved),
                "attributes": state_attrs,
            },
        )
        _post_json(
            base,
            token,
            "/states/sensor.ekstrehub_last_sync",
            {
                "state": now_iso,
                "attributes": state_attrs,
            },
        )
        log.info("ha_notify_sent run_id=%s saved=%d source=%s", run_id, saved, source)
        return True
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="ignore")[:300]
        except Exception:
            body = ""
        if exc.code == 401:
            log.warning(
                "ha_notify_failed run_id=%s err=unauthorized status=401 base=%s "
                "hint=enable_hassio_api_and_homeassistant_api body=%s",
                run_id,
                base,
                body or "-",
            )
            return False
        log.warning(
            "ha_notify_failed run_id=%s status=%s reason=%s base=%s body=%s",
            run_id,
            exc.code,
            exc.reason,
            base,
            body or "-",
        )
        return False
    except (urllib.error.URLError, RuntimeError, OSError) as exc:
        log.warning("ha_notify_failed run_id=%s err=%s", run_id, exc)
        return False

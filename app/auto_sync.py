"""Automatic mail sync scheduler.

Settings are persisted to a JSON sidecar file next to the database.
The background task wakes up every minute and fires a sync if the
configured interval has elapsed.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("ekstrehub.auto_sync")

# Resolved at runtime relative to the DB file (or CWD as fallback)
_SETTINGS_PATH: Path | None = None

_DEFAULT: dict[str, Any] = {
    "enabled": False,
    "interval_minutes": 60,
    "last_auto_sync_at": None,
}


def _settings_path() -> Path:
    global _SETTINGS_PATH
    if _SETTINGS_PATH is not None:
        return _SETTINGS_PATH
    db_url = os.getenv("DB_URL", "")
    # sqlite:///./dev-local.db  or  sqlite:////abs/path.db
    if db_url.startswith("sqlite"):
        db_file = db_url.replace("sqlite:///", "").lstrip("/").lstrip("./")
        candidate = Path(db_file).parent / "auto_sync_settings.json"
        _SETTINGS_PATH = candidate
    else:
        _SETTINGS_PATH = Path("auto_sync_settings.json")
    return _SETTINGS_PATH


def load_settings() -> dict[str, Any]:
    path = _settings_path()
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            # Merge with defaults to handle missing keys from older files
            return {**_DEFAULT, **data}
        except Exception:
            pass
    return dict(_DEFAULT)


def save_settings(settings: dict[str, Any]) -> None:
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def get_auto_sync_status() -> dict[str, Any]:
    """Return current settings plus computed next_sync_at."""
    s = load_settings()
    next_sync_at: str | None = None
    if s["enabled"] and s["interval_minutes"]:
        if s["last_auto_sync_at"]:
            try:
                last = datetime.fromisoformat(s["last_auto_sync_at"])
                from datetime import timedelta
                nxt = last + timedelta(minutes=s["interval_minutes"])
                next_sync_at = nxt.isoformat()
            except Exception:
                pass
        else:
            # Never synced → next sync is "now" (will fire on next tick)
            next_sync_at = datetime.now(timezone.utc).isoformat()
    return {**s, "next_sync_at": next_sync_at}


def update_settings(enabled: bool | None, interval_minutes: int | None) -> dict[str, Any]:
    s = load_settings()
    if enabled is not None:
        s["enabled"] = enabled
    if interval_minutes is not None:
        if interval_minutes not in (5, 15, 30, 60, 120, 240, 480):
            raise ValueError("interval_minutes must be one of: 5,15,30,60,120,240,480")
        s["interval_minutes"] = interval_minutes
    save_settings(s)
    return get_auto_sync_status()


def _mark_synced() -> None:
    s = load_settings()
    s["last_auto_sync_at"] = datetime.now(timezone.utc).isoformat()
    save_settings(s)


async def run_scheduler(session_factory_getter, ingestion_service_factory) -> None:  # type: ignore[type-arg]
    """Background asyncio task — runs forever, fires sync when due."""
    log.info("auto_sync_scheduler_started")
    while True:
        try:
            await asyncio.sleep(60)  # check every minute
            s = load_settings()
            if not s["enabled"]:
                continue

            interval_s = int(s["interval_minutes"]) * 60
            last_raw = s.get("last_auto_sync_at")
            now = datetime.now(timezone.utc)

            if last_raw:
                last = datetime.fromisoformat(last_raw)
                elapsed = (now - last).total_seconds()
                if elapsed < interval_s:
                    continue  # not yet time

            log.info("auto_sync_triggered interval_minutes=%s", s["interval_minutes"])
            _mark_synced()

            # Run sync for all active mail accounts
            session_factory = session_factory_getter()
            with session_factory() as session:
                from app.db.models import MailAccount
                from sqlalchemy import select as sa_select
                accounts = session.scalars(
                    sa_select(MailAccount).where(MailAccount.is_active == True)  # noqa: E712
                ).all()

            for account in accounts:
                try:
                    svc = ingestion_service_factory(account)
                    summary = await asyncio.to_thread(svc.run_ingestion_for_account, account.id)
                    log.info(
                        "auto_sync_completed account_id=%d saved=%d",
                        account.id,
                        summary.saved_documents,
                    )
                except Exception as exc:
                    log.error("auto_sync_account_failed account_id=%d error=%s", account.id, exc)

        except asyncio.CancelledError:
            log.info("auto_sync_scheduler_stopped")
            return
        except Exception as exc:
            log.error("auto_sync_scheduler_error error=%s", exc)
            await asyncio.sleep(30)  # back off on unexpected errors

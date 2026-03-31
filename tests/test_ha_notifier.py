from __future__ import annotations

import json

from app import ha_notifier


def test_notify_skips_when_no_saved_docs(monkeypatch) -> None:
    monkeypatch.setenv("SUPERVISOR_TOKEN", "token")
    called = {"n": 0}

    def _fake_post(*_args, **_kwargs):
        called["n"] += 1

    monkeypatch.setattr(ha_notifier, "_post_json", _fake_post)
    ok = ha_notifier.notify_new_statements_to_ha(
        {"saved_documents": 0},
        account_label="A",
        imap_user="u@example.com",
        source="manual_sync",
    )
    assert ok is False
    assert called["n"] == 0


def test_notify_skips_without_supervisor_token(monkeypatch) -> None:
    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)
    ok = ha_notifier.notify_new_statements_to_ha(
        {"saved_documents": 2},
        account_label="A",
        imap_user="u@example.com",
        source="manual_sync",
    )
    assert ok is False


def test_notify_posts_service_and_sensor_states(monkeypatch) -> None:
    monkeypatch.setenv("SUPERVISOR_TOKEN", "token")
    monkeypatch.setenv("HA_CORE_API_URL", "http://supervisor/core/api")
    sent: list[tuple[str, dict]] = []

    def _fake_post(_base: str, _token: str, path: str, payload: dict):
        sent.append((path, json.loads(json.dumps(payload))))

    monkeypatch.setattr(ha_notifier, "_post_json", _fake_post)
    ok = ha_notifier.notify_new_statements_to_ha(
        {
            "run_id": 9,
            "saved_documents": 3,
            "scanned_messages": 12,
            "processed_messages": 4,
            "duplicate_messages": 8,
            "failed_messages": 0,
        },
        account_label="Primary Gmail",
        imap_user="kart@catal.net",
        source="auto_sync",
    )
    assert ok is True
    assert [x[0] for x in sent] == [
        "/services/persistent_notification/create",
        "/states/sensor.ekstrehub_new_statements",
        "/states/sensor.ekstrehub_last_sync",
    ]
    assert sent[0][1]["title"] == "EkstreHub: Yeni ekstre bulundu"
    assert sent[1][1]["attributes"]["saved_documents"] == 3
    assert sent[2][1]["attributes"]["source"] == "auto_sync"

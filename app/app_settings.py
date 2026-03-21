"""Persistent application settings stored in a JSON sidecar file.

Covers LLM/AI parser configuration that users can update at runtime
without restarting the server. Values in this file override the
environment-variable defaults set in config.py.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger("ekstrehub.app_settings")

_SETTINGS_PATH: Path | None = None

_DEFAULT: dict[str, Any] = {
    "llm_provider": "ollama",        # "ollama" | "openai" | "custom"
    "llm_api_url": "",               # e.g. https://api.openai.com/v1
    "llm_api_key": "",               # sk-... for OpenAI, empty for Ollama
    "llm_model": "gpt-4o-mini",     # model name
    "llm_timeout_seconds": 60,       # request timeout
    "llm_enabled": True,             # whether to use LLM fallback at all
    "llm_min_tx_threshold": 0,       # run LLM also if regex finds fewer tx than this (0 = only on 0 tx)
}

_PROVIDER_DEFAULTS = {
    "ollama": {
        "llm_api_url": "http://localhost:11434/v1",
        "llm_api_key": "",
        "llm_model": "qwen2.5:7b",
        "llm_timeout_seconds": 180,
    },
    "openai": {
        "llm_api_url": "https://api.openai.com/v1",
        "llm_api_key": "",
        "llm_model": "gpt-4o-mini",
        # Büyük PDF'ler + OpenAI gecikmesi için 60s sık yetmez (timeout → boş ekstre)
        "llm_timeout_seconds": 180,
    },
    "custom": {
        "llm_api_url": "",
        "llm_api_key": "",
        "llm_model": "",
        "llm_timeout_seconds": 120,
    },
}


def _settings_path() -> Path:
    global _SETTINGS_PATH
    if _SETTINGS_PATH is not None:
        return _SETTINGS_PATH
    db_url = os.getenv("DB_URL", "")
    if db_url.startswith("sqlite"):
        path_part = db_url.replace("sqlite:///", "").replace("sqlite://", "")
        if path_part.startswith("//"):
            path_part = "/" + path_part[2:]
        elif path_part.startswith("/"):
            pass
        else:
            path_part = path_part.lstrip("./")
        db_path = Path(path_part) if path_part else Path(".")
        candidate = (db_path.parent if db_path.name else db_path) / "app_settings.json"
        _SETTINGS_PATH = candidate
    else:
        _SETTINGS_PATH = Path("app_settings.json")
    return _SETTINGS_PATH


def load() -> dict[str, Any]:
    """Load settings, merging with defaults. Also overlays env vars as initial values."""
    path = _settings_path()
    data: dict[str, Any] = {}
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass

    merged = {**_DEFAULT, **data}

    # If no settings file yet, seed from environment variables
    if not path.exists():
        env_url = os.getenv("LLM_API_URL", "").strip()
        env_key = os.getenv("LLM_API_KEY", "").strip()
        env_model = os.getenv("LLM_MODEL", "").strip()
        if env_url:
            merged["llm_api_url"] = env_url
        if env_key:
            merged["llm_api_key"] = env_key
        if env_model:
            merged["llm_model"] = env_model

    return merged


def save(settings: dict[str, Any]) -> None:
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
    log.info("app_settings_saved path=%s", path)


def get_llm_config() -> dict[str, Any]:
    """Return the effective LLM config (merged file + env overrides)."""
    s = load()
    # Env vars always win over saved settings (for deployment overrides)
    env_url = os.getenv("LLM_API_URL", "").strip()
    env_key = os.getenv("LLM_API_KEY", "").strip()
    env_model = os.getenv("LLM_MODEL", "").strip()
    return {
        "llm_enabled": s.get("llm_enabled", True),
        "llm_provider": s.get("llm_provider", "ollama"),
        "llm_api_url": env_url or s.get("llm_api_url", ""),
        "llm_api_key": env_key or s.get("llm_api_key", ""),
        "llm_model": env_model or s.get("llm_model", "gpt-4o-mini"),
        "llm_timeout_seconds": s.get("llm_timeout_seconds", 60),
        "llm_min_tx_threshold": s.get("llm_min_tx_threshold", 0),
    }


def update(patch: dict[str, Any]) -> dict[str, Any]:
    """Merge patch into current settings and save."""
    s = load()
    allowed = {"llm_provider", "llm_api_url", "llm_api_key", "llm_model",
               "llm_timeout_seconds", "llm_enabled", "llm_min_tx_threshold"}
    for k, v in patch.items():
        if k in allowed:
            s[k] = v
    save(s)
    return get_api_response()


def get_api_response() -> dict[str, Any]:
    """Return settings for the API — mask the API key."""
    cfg = get_llm_config()
    s = load()
    key = cfg["llm_api_key"]
    masked_key = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else ("*" * len(key) if key else "")
    return {
        "llm_enabled": cfg["llm_enabled"],
        "llm_provider": s.get("llm_provider", "ollama"),
        "llm_api_url": cfg["llm_api_url"],
        "llm_api_key_set": bool(key),
        "llm_api_key_masked": masked_key,
        "llm_model": cfg["llm_model"],
        "llm_timeout_seconds": cfg["llm_timeout_seconds"],
        "llm_min_tx_threshold": cfg["llm_min_tx_threshold"],
        "provider_defaults": _PROVIDER_DEFAULTS,
    }

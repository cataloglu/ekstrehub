import os
from dataclasses import dataclass
from functools import lru_cache


class ConfigError(ValueError):
    """Raised when required runtime configuration is invalid."""


def _parse_bool(raw: str, default: bool = False) -> bool:
    if raw is None:
        return default
    normalized = raw.strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def mask_secret(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    return f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"


@dataclass(frozen=True)
class AppConfig:
    app_env: str
    log_level: str
    api_host: str
    api_port: int
    app_secret_key: str
    db_url: str
    mail_ingestion_enabled: bool
    imap_host: str
    imap_port: int
    imap_user: str
    imap_password: str
    imap_mailbox: str
    imap_unseen_only: bool
    imap_fetch_limit: int
    imap_retry_count: int
    imap_retry_backoff_seconds: float
    gmail_oauth_client_id: str
    gmail_oauth_client_secret: str
    gmail_oauth_redirect_proxy_url: str  # when set, OAuth uses this as redirect_uri (single URI for all users)
    # LLM parser (optional — leave empty to use regex fallback)
    llm_api_url: str        # e.g. http://localhost:11434/v1 for Ollama
    llm_model: str          # e.g. qwen2.5:7b
    llm_api_key: str        # empty for Ollama, sk-... for OpenAI
    llm_timeout_seconds: int


@lru_cache(maxsize=1)
def get_settings() -> AppConfig:
    log_level = os.getenv("LOG_LEVEL", "info").strip().lower()
    allowed_log_levels = {"trace", "debug", "info", "warning", "error", "critical"}
    if log_level not in allowed_log_levels:
        raise ConfigError(
            "Invalid LOG_LEVEL. Expected one of: trace, debug, info, warning, error, critical."
        )

    app_env = os.getenv("APP_ENV", "development").strip().lower()
    api_host = os.getenv("API_HOST", "0.0.0.0").strip()
    api_port_raw = os.getenv("API_PORT", "8000").strip()
    db_url = os.getenv("DB_URL", "").strip()
    app_secret_key = os.getenv("APP_SECRET_KEY", "").strip()
    mail_ingestion_enabled = _parse_bool(os.getenv("MAIL_INGESTION_ENABLED"), default=True)

    try:
        api_port = int(api_port_raw)
    except ValueError as exc:
        raise ConfigError("API_PORT must be a valid integer.") from exc

    imap_host = os.getenv("IMAP_HOST", "").strip()
    imap_port_raw = os.getenv("IMAP_PORT", "993").strip()
    imap_user = os.getenv("IMAP_USER", "").strip()
    imap_password = os.getenv("IMAP_PASSWORD", "").strip()
    imap_mailbox = os.getenv("IMAP_MAILBOX", "INBOX").strip()
    imap_unseen_only = _parse_bool(os.getenv("IMAP_UNSEEN_ONLY"), default=True)
    imap_fetch_limit_raw = os.getenv("IMAP_FETCH_LIMIT", "20").strip()
    imap_retry_count_raw = os.getenv("IMAP_RETRY_COUNT", "3").strip()
    imap_retry_backoff_raw = os.getenv("IMAP_RETRY_BACKOFF_SECONDS", "1.5").strip()
    gmail_oauth_client_id = (
        os.getenv("GMAIL_OAUTH_CLIENT_ID", "").strip()
        or os.getenv("EKSTREHUB_BUILTIN_GMAIL_CLIENT_ID", "").strip()
    )
    gmail_oauth_client_secret = (
        os.getenv("GMAIL_OAUTH_CLIENT_SECRET", "").strip()
        or os.getenv("EKSTREHUB_BUILTIN_GMAIL_CLIENT_SECRET", "").strip()
    )
    gmail_oauth_redirect_proxy_url = os.getenv("OAUTH_REDIRECT_PROXY_URL", "").strip()
    llm_api_url = os.getenv("LLM_API_URL", "").strip()
    llm_model = os.getenv("LLM_MODEL", "qwen2.5:7b").strip()
    llm_api_key = os.getenv("LLM_API_KEY", "").strip()
    llm_timeout_raw = os.getenv("LLM_TIMEOUT_SECONDS", "120").strip()
    try:
        llm_timeout_seconds = int(llm_timeout_raw)
    except ValueError:
        llm_timeout_seconds = 120

    try:
        imap_port = int(imap_port_raw)
    except ValueError as exc:
        raise ConfigError("IMAP_PORT must be a valid integer.") from exc
    try:
        imap_fetch_limit = int(imap_fetch_limit_raw)
    except ValueError as exc:
        raise ConfigError("IMAP_FETCH_LIMIT must be a valid integer.") from exc
    if imap_fetch_limit <= 0:
        raise ConfigError("IMAP_FETCH_LIMIT must be greater than 0.")
    try:
        imap_retry_count = int(imap_retry_count_raw)
    except ValueError as exc:
        raise ConfigError("IMAP_RETRY_COUNT must be a valid integer.") from exc
    if imap_retry_count < 1:
        raise ConfigError("IMAP_RETRY_COUNT must be at least 1.")
    try:
        imap_retry_backoff_seconds = float(imap_retry_backoff_raw)
    except ValueError as exc:
        raise ConfigError("IMAP_RETRY_BACKOFF_SECONDS must be a valid number.") from exc
    if imap_retry_backoff_seconds <= 0:
        raise ConfigError("IMAP_RETRY_BACKOFF_SECONDS must be greater than 0.")

    missing: list[str] = []
    if not db_url:
        # Default to SQLite in /data for HA add-on, or local file for development
        import pathlib
        data_dir = pathlib.Path("/data")
        if data_dir.is_dir():
            db_url = "sqlite:////data/ekstrehub.db"
        else:
            db_url = "sqlite:///./dev-local.db"

    if app_env == "production" and not app_secret_key:
        # Secret key is optional – only needed for signed cookies/JWT (not used yet)
        pass

    # IMAP credentials are optional: mail accounts are managed through the UI.
    # Legacy single-account mode (env var config) still works if all three are set.

    if missing:
        raise ConfigError(f"Missing required environment variables: {', '.join(missing)}")

    return AppConfig(
        app_env=app_env,
        log_level=log_level,
        api_host=api_host,
        api_port=api_port,
        app_secret_key=app_secret_key,
        db_url=db_url,
        mail_ingestion_enabled=mail_ingestion_enabled,
        imap_host=imap_host,
        imap_port=imap_port,
        imap_user=imap_user,
        imap_password=imap_password,
        imap_mailbox=imap_mailbox,
        imap_unseen_only=imap_unseen_only,
        imap_fetch_limit=imap_fetch_limit,
        imap_retry_count=imap_retry_count,
        imap_retry_backoff_seconds=imap_retry_backoff_seconds,
        gmail_oauth_client_id=gmail_oauth_client_id,
        gmail_oauth_client_secret=gmail_oauth_client_secret,
        gmail_oauth_redirect_proxy_url=gmail_oauth_redirect_proxy_url,
        llm_api_url=llm_api_url,
        llm_model=llm_model,
        llm_api_key=llm_api_key,
        llm_timeout_seconds=llm_timeout_seconds,
    )

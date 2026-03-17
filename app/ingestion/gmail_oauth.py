from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from app.config import AppConfig


class GmailOAuthError(RuntimeError):
    """Raised when Gmail OAuth token refresh fails."""


def _parse_oauth_error(body: str) -> str:
    try:
        data = json.loads(body)
        err = data.get("error", "")
        desc = data.get("error_description", "")
        if err == "invalid_grant" or "revoked" in (desc or "").lower() or "expired" in (desc or "").lower():
            return "Token süresi doldu veya iptal edildi. Hesabı silip yeniden ekleyin."
        if desc:
            return desc
        if err:
            return str(err)
    except Exception:
        pass
    return "Google OAuth hatası."


def refresh_access_token(settings: AppConfig, refresh_token: str) -> str:
    if not settings.gmail_oauth_client_id or not settings.gmail_oauth_client_secret:
        raise GmailOAuthError("Gmail OAuth client credentials are not configured.")

    payload = urlencode(
        {
            "client_id": settings.gmail_oauth_client_id,
            "client_secret": settings.gmail_oauth_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")

    request = Request(
        "https://oauth2.googleapis.com/token",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
            parsed = json.loads(body)
    except HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else ""
        msg = _parse_oauth_error(body) if body else str(exc)
        raise GmailOAuthError(msg) from exc
    except Exception as exc:
        raise GmailOAuthError(f"Token refresh request failed: {exc}") from exc

    access_token = parsed.get("access_token")
    if not access_token:
        err_msg = _parse_oauth_error(json.dumps(parsed)) if parsed else "Yanıtta access_token yok."
        raise GmailOAuthError(err_msg)
    return access_token

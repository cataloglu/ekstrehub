from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config import AppConfig


class GmailOAuthError(RuntimeError):
    """Raised when Gmail OAuth token refresh fails."""


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
    except Exception as exc:
        raise GmailOAuthError(f"Token refresh request failed: {exc}") from exc

    access_token = parsed.get("access_token")
    if not access_token:
        raise GmailOAuthError("Token refresh response did not include access_token.")
    return access_token

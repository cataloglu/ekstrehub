"""Gmail OAuth2 authorization flow (installed-app / loopback redirect).

Flow:
  1. GET /api/oauth/gmail/start        → redirects browser to Google consent screen
  2. Google redirects to /api/oauth/gmail/callback?code=...
  3. We exchange code for tokens, create/update MailAccount, redirect UI to success page.
"""
from __future__ import annotations

import json
from urllib.parse import urlencode, urlparse, parse_qs
from urllib.request import Request, urlopen

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_SCOPES = "https://mail.google.com/"


def build_auth_url(client_id: str, redirect_uri: str, state: str = "") -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GMAIL_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
    }
    if state:
        params["state"] = state
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_tokens(
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> dict:
    payload = urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")

    req = Request(
        GOOGLE_TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))

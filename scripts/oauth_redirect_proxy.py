#!/usr/bin/env python3
"""
Minimal OAuth redirect proxy for Gmail OAuth when using a single shared Client ID.

Google allows only one redirect URI per client (or a fixed list). When each user
has a different URL (e.g. Home Assistant Ingress), we register this proxy as the
redirect_uri. Google redirects here with code & state; state = base64(user_callback_url).
We redirect the browser to that URL with the code so the user's add-on can exchange it.

Deploy anywhere (Cloud Run, Fly.io, etc.) and set OAUTH_REDIRECT_PROXY_URL in the
add-on to this server's /callback URL. Optionally set EKSTREHUB_BUILTIN_GMAIL_*
so end users never need to configure Client ID/Secret.

Usage:
  python scripts/oauth_redirect_proxy.py   # listens on 0.0.0.0:9090
  OAUTH_PROXY_PORT=9090 python scripts/oauth_redirect_proxy.py
"""
from __future__ import annotations

import base64
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlencode, urlparse


def decode_state(state: str) -> str | None:
    if not state:
        return None
    try:
        pad = 4 - len(state) % 4
        if pad != 4:
            state = state + ("=" * pad)
        return base64.urlsafe_b64decode(state).decode("utf-8")
    except Exception:
        return None


class OAuthProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/callback" and parsed.path != "/":
            self.send_response(404)
            self.end_headers()
            return
        qs = parse_qs(parsed.query)
        code = (qs.get("code") or [None])[0]
        state = (qs.get("state") or [None])[0]
        error = (qs.get("error") or [None])[0]

        target = decode_state(state) if state else None
        if not target:
            self.send_response(400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Missing or invalid state.")
            return

        sep = "&" if "?" in target else "?"
        if error:
            params = urlencode({"oauth": "error", "reason": error})
        else:
            params = urlencode({"code": code}) if code else ""
        if params:
            target = f"{target}{sep}{params}"

        self.send_response(302)
        self.send_header("Location", target)
        self.end_headers()

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    port = int(os.getenv("OAUTH_PROXY_PORT", "9090"))
    with HTTPServer(("0.0.0.0", port), OAuthProxyHandler) as httpd:
        print(f"OAuth redirect proxy listening on http://0.0.0.0:{port}/callback")
        httpd.serve_forever()

from __future__ import annotations

import os
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlencode, urlparse, parse_qs

import requests
from dotenv import load_dotenv, set_key

load_dotenv()

REDIRECT_URI = os.getenv("THREADS_REDIRECT_URI", "http://localhost:8765/callback")
SCOPE = "threads_basic,threads_content_publish"
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")

_auth_code: str | None = None


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        global _auth_code
        query = parse_qs(urlparse(self.path).query)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        if "code" in query:
            _auth_code = query["code"][0]
            self.wfile.write(b"<html><body>Ok, mozhna zakryty vkladku.</body></html>")
        else:
            error = query.get("error_description", ["unknown error"])[0]
            self.wfile.write(f"<html><body>Error: {error}</body></html>".encode())

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass


def get_auth_code(app_id: str) -> str:
    params = {
        "client_id": app_id,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "response_type": "code",
    }
    auth_url = f"https://threads.net/oauth/authorize?{urlencode(params)}"
    print(f"Open this URL and log in:\n{auth_url}\n")
    webbrowser.open(auth_url)

    port = int(urlparse(REDIRECT_URI).port or 8765)
    server = HTTPServer(("localhost", port), CallbackHandler)
    while _auth_code is None:
        server.handle_request()
    return _auth_code


def exchange_code(app_id: str, app_secret: str, code: str) -> tuple[str, str]:
    resp = requests.post(
        "https://graph.threads.net/oauth/access_token",
        data={
            "client_id": app_id,
            "client_secret": app_secret,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "code": code,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["access_token"], str(data["user_id"])


def exchange_long_lived(app_secret: str, short_token: str) -> str:
    resp = requests.get(
        "https://graph.threads.net/access_token",
        params={
            "grant_type": "th_exchange_token",
            "client_secret": app_secret,
            "access_token": short_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def main() -> int:
    app_id = os.getenv("THREADS_APP_ID")
    app_secret = os.getenv("THREADS_APP_SECRET")
    if not app_id or not app_secret:
        print("Missing THREADS_APP_ID / THREADS_APP_SECRET in .env", file=sys.stderr)
        return 1

    code = get_auth_code(app_id)
    short_token, user_id = exchange_code(app_id, app_secret, code)
    long_token = exchange_long_lived(app_secret, short_token)

    print(f"THREADS_ACCESS_TOKEN={long_token}")
    print(f"THREADS_USER_ID={user_id}")

    set_key(ENV_PATH, "THREADS_ACCESS_TOKEN", long_token)
    set_key(ENV_PATH, "THREADS_USER_ID", user_id)
    print(f"\nWritten to {ENV_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

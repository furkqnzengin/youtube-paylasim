#!/usr/bin/env python3
"""Bir kerelik: kendi bilgisayarında çalıştır, YT_REFRESH_TOKEN değerini üretir.

  python scripts/get_token.py client_secret.json

client_secret.json: Google Cloud Console > Credentials > OAuth client ID
(tür: Desktop app) ekranından indirilen dosya. Ek paket gerekmez.
"""
import http.server
import json
import secrets
import sys
import urllib.parse
import urllib.request
import webbrowser

SCOPE = "https://www.googleapis.com/auth/youtube.upload"
PORT = 8765


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding="utf-8") as fh:
        data = json.load(fh)
    client = data.get("installed") or data.get("web")
    redirect = f"http://127.0.0.1:{PORT}"
    state = secrets.token_urlsafe(16)
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client["client_id"],
        "redirect_uri": redirect,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    })
    result = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("state", [""])[0] == state and "code" in q:
                result["code"] = q["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("Tamam, bu sekmeyi kapatabilirsin.".encode())

        def log_message(self, *a):
            pass

    print("Tarayıcı açılmazsa bu adresi aç:\n" + url + "\n")
    webbrowser.open(url)
    srv = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
    while "code" not in result:
        srv.handle_request()

    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=urllib.parse.urlencode({
            "code": result["code"],
            "client_id": client["client_id"],
            "client_secret": client["client_secret"],
            "redirect_uri": redirect,
            "grant_type": "authorization_code",
        }).encode(),
    )
    tok = json.load(urllib.request.urlopen(req))
    print("GitHub secret olarak ekle:\n")
    print("YT_CLIENT_ID     =", client["client_id"])
    print("YT_CLIENT_SECRET =", client["client_secret"])
    print("YT_REFRESH_TOKEN =", tok.get("refresh_token"))


if __name__ == "__main__":
    main()

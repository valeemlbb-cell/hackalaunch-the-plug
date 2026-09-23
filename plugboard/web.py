"""Local dashboard. Binds to 127.0.0.1 by default and refuses to be useful anywhere else.

The approve / reject / send buttons post back to this server, which calls exactly the same
approval functions the CLI calls - there is no second, looser path to a send. A per-process
CSRF token is embedded in each form and checked on every POST, so a page left open in a
browser cannot be driven by another site.
"""
from __future__ import annotations

import secrets
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import approval, tracking, ui
from .senders import build_sender

MAX_BODY_BYTES = 64 * 1024


def _campaign_or_none(pb):
    rows = pb.store.read("campaigns")
    if not rows:
        return None
    return pb.campaign(rows[-1]["campaign_id"])


class Handler(BaseHTTPRequestHandler):
    server_version = "Plugboard"
    pb = None
    token = ""

    def log_message(self, *args):
        pass  # the audit trail is the log; request spam is noise

    # ------------------------------------------------------------------ GET
    def do_GET(self):
        if self.path.split("?")[0] not in ("/", "/index.html"):
            return self._send(404, "text/plain", "not found")
        campaign = _campaign_or_none(self.pb)
        matches = self.pb.stored_matches(campaign.campaign_id) if campaign else []
        matches = [m for m in matches if not m.excluded]
        drafts = self.pb.drafts()
        deals = [d for d in tracking.all_deals(self.pb.store)
                 if not campaign or d.campaign_id == campaign.campaign_id]
        html = ui.page(self.pb, campaign, matches, drafts, deals, self.token)
        return self._send(200, "text/html; charset=utf-8", html)

    # ----------------------------------------------------------------- POST
    def do_POST(self):
        action = self.path.split("?")[0]
        if action not in ("/approve", "/reject", "/send"):
            return self._send(404, "text/plain", "not found")
        form = self._form()
        if not secrets.compare_digest(form.get("token", ""), self.token):
            return self._send(403, "text/plain", "bad or missing CSRF token")
        draft_id = form.get("draft_id", "")
        operator = self.pb.settings.operator or "dashboard-operator"
        try:
            if action == "/approve":
                approval.approve(self.pb.store, self.pb.secret, draft_id, operator)
            elif action == "/reject":
                approval.reject(self.pb.store, draft_id, operator, "rejected from dashboard")
            else:
                row = self.pb.store.find("drafts", "draft_id", draft_id) or {}
                sender = build_sender(self.pb.settings, self.pb.contact_for(row.get("creator_id", "")))
                approval.send(self.pb.store, self.pb.secret, draft_id, sender)
        except approval.ApprovalError as exc:
            self.pb.store.log("dashboard.refused", draft_id, action=action, reason=str(exc))
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    # --------------------------------------------------------------- helpers
    def _form(self) -> dict:
        try:
            length = min(int(self.headers.get("Content-Length", "0")), MAX_BODY_BYTES)
        except ValueError:
            return {}
        raw = self.rfile.read(length).decode("utf-8", "replace") if length else ""
        return {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}

    def _send(self, status: int, content_type: str, body: str):
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(payload)


def build_server(pb, host: str = "127.0.0.1", port: int = 8799) -> ThreadingHTTPServer:
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise RuntimeError(
            f"refusing to bind {host}: the dashboard has no authentication and holds an approval "
            "gate. Keep it on localhost and tunnel if you need remote access.")
    handler = type("BoundHandler", (Handler,), {"pb": pb, "token": secrets.token_urlsafe(24)})
    return ThreadingHTTPServer((host, port), handler)


def serve(pb, host: str = "127.0.0.1", port: int = 8799) -> None:
    server = build_server(pb, host, port)
    print(f"Plugboard dashboard on http://{host}:{port}  (Ctrl-C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

"""The dashboard is the second door to a send, so it gets the same scrutiny as the CLI."""
from __future__ import annotations

import threading
import urllib.error
import urllib.parse
import urllib.request

import pytest

from plugboard import approval, matching
from plugboard.app import Plugboard
from plugboard.outreach import compose
from plugboard.web import build_server

from .conftest import SAMPLE_BRIEF, SEED


@pytest.fixture
def live(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pb = Plugboard(workspace=str(tmp_path / "ws"), catalog_path=SEED, use_llm=False)
    from plugboard.brief import parse_brief
    with open(SAMPLE_BRIEF, encoding="utf-8") as fh:
        campaign = parse_brief(fh.read(), "kilat")
    pb.save_campaign(campaign)
    pb.run_matching(campaign, limit=3)
    creator = pb.creator("c014")
    draft = compose(campaign, creator, matching.match_one(campaign, creator))
    approval.queue(pb.store, [draft])

    server = build_server(pb, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    token = server.RequestHandlerClass.token
    yield pb, base, token
    server.shutdown()
    server.server_close()


def get(url: str) -> str:
    with urllib.request.urlopen(url, timeout=10) as response:
        return response.read().decode("utf-8")


def post(url: str, fields: dict):
    data = urllib.parse.urlencode(fields).encode("utf-8")
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


def test_page_shows_the_pipeline_and_the_pending_draft(live):
    _, base, _ = live
    html = get(base + "/")
    assert "Human approval gate" in html
    assert "d-kilat-c014" in html
    assert "DRY RUN" in html
    assert "devnet" in html


def test_page_escapes_draft_content(live):
    pb, base, _ = live
    from dataclasses import replace
    row = pb.store.find("drafts", "draft_id", "d-kilat-c014")
    from plugboard.models import Draft
    draft = Draft(**{k: v for k, v in row.items() if k in Draft.__dataclass_fields__})
    pb.store.upsert("drafts", "draft_id", replace(draft, body="<script>alert(1)</script>" + draft.body))
    html = get(base + "/")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_post_without_the_csrf_token_is_rejected(live):
    pb, base, _ = live
    assert post(base + "/approve", {"draft_id": "d-kilat-c014"}) == 403
    assert pb.store.find("drafts", "draft_id", "d-kilat-c014")["status"] == "pending"


def test_post_with_a_wrong_token_is_rejected(live):
    pb, base, _ = live
    assert post(base + "/approve", {"draft_id": "d-kilat-c014", "token": "nope"}) == 403
    assert pb.store.find("drafts", "draft_id", "d-kilat-c014")["status"] == "pending"


def test_approving_then_sending_through_the_dashboard_works(live):
    pb, base, token = live
    post(base + "/approve", {"draft_id": "d-kilat-c014", "token": token})
    assert pb.store.find("drafts", "draft_id", "d-kilat-c014")["status"] == "approved"
    post(base + "/send", {"draft_id": "d-kilat-c014", "token": token})
    row = pb.store.find("drafts", "draft_id", "d-kilat-c014")
    assert row["status"] == "sent" and row["send_ref"].endswith(".eml")


def test_sending_without_approving_is_refused_and_logged(live):
    pb, base, token = live
    post(base + "/send", {"draft_id": "d-kilat-c014", "token": token})
    assert pb.store.find("drafts", "draft_id", "d-kilat-c014")["status"] == "pending"
    assert any(e["kind"] == "dashboard.refused" for e in pb.store.events())


def test_rejecting_through_the_dashboard(live):
    pb, base, token = live
    post(base + "/reject", {"draft_id": "d-kilat-c014", "token": token})
    assert pb.store.find("drafts", "draft_id", "d-kilat-c014")["status"] == "rejected"


def test_unknown_paths_404(live):
    _, base, _ = live
    try:
        get(base + "/admin")
        assert False, "should have 404ed"
    except urllib.error.HTTPError as exc:
        assert exc.code == 404


def test_security_headers_are_present(live):
    _, base, _ = live
    with urllib.request.urlopen(base + "/", timeout=10) as response:
        headers = dict(response.headers)
    assert headers["X-Frame-Options"] == "DENY"
    assert "default-src 'none'" in headers["Content-Security-Policy"]

"""The whole loop through the real CLI, exactly as the demo runs it.

This is the test that would catch "each module works but the pipeline does not".
"""
from __future__ import annotations

import json
import os

import pytest

from plugboard.cli import main

from .conftest import SAMPLE_BRIEF, SEED


@pytest.fixture
def run(tmp_path, monkeypatch):
    workspace = str(tmp_path / "ws")
    monkeypatch.chdir(tmp_path)

    def _run(*argv):
        return main(["--workspace", workspace, "--catalog", SEED, "--no-llm", *argv])
    _run.workspace = workspace
    return _run


def read(workspace, name):
    path = os.path.join(workspace, f"{name}.json")
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def test_full_pipeline_brief_to_report(run, capsys):
    assert run("brief", SAMPLE_BRIEF, "--id", "kilat") == 0
    assert run("match", "--campaign", "kilat", "--limit", "4", "--show-excluded") == 0
    assert run("draft", "--campaign", "kilat", "--limit", "3") == 0
    assert run("queue") == 0
    assert run("show", "d-kilat-c014") == 0
    assert run("creators") == 0

    out = capsys.readouterr().out
    assert "BRIEF -> CAMPAIGN" in out and "Kilat" in out
    assert "authenticity check failed" in out          # the filtered-out creators are shown
    assert "staged for human approval" in out
    assert "Nothing has been sent" in out

    drafts = read(run.workspace, "drafts")
    assert drafts and all(d["status"] == "pending" for d in drafts)
    assert all(not d["approval_token"] for d in drafts)


def test_send_before_approve_is_refused_from_the_cli(run, capsys):
    run("brief", SAMPLE_BRIEF, "--id", "kilat")
    run("match", "--campaign", "kilat", "--limit", "3")
    run("draft", "--campaign", "kilat", "--limit", "1")
    capsys.readouterr()
    assert run("send", "d-kilat-c014") == 1
    assert "human must approve" in capsys.readouterr().out


def test_approve_send_reply_deal_result_report(run, capsys):
    run("brief", SAMPLE_BRIEF, "--id", "kilat")
    run("match", "--campaign", "kilat", "--limit", "3")
    run("draft", "--campaign", "kilat", "--limit", "1")
    assert run("approve", "d-kilat-c014", "--by", "henggar") == 0
    assert run("send", "d-kilat-c014") == 0
    assert run("reply", "d-kilat-c014", "--text", "tertarik kak, rate aku 260") == 0
    assert run("deal", "open", "--campaign", "kilat", "--creator", "c014", "--fee", "260") == 0
    assert run("deal", "status", "deal-kilat-c014", "--status", "agreed") == 0
    assert run("deal", "deliverable", "deal-kilat-c014",
               "--desc", "2 x TikTok short", "--due", "2026-10-05") == 0
    assert run("deal", "status", "deal-kilat-c014", "--status", "running") == 0
    assert run("deal", "mark", "deal-kilat-c014", "--deliverable", "deal-kilat-c014-d1",
               "--state", "live", "--proof", "https://example.invalid/p/1") == 0
    assert run("result", "deal-kilat-c014", "--deliverable", "deal-kilat-c014-d1",
               "--platform", "tiktok", "--url", "https://example.invalid/p/1",
               "--views", "74000", "--clicks", "1900", "--conversions", "210") == 0
    assert run("report", "--campaign", "kilat", "--json") == 0
    assert run("due", "--days", "30", "--as-of", "2026-10-01") == 0
    assert run("events", "--limit", "50") == 0

    out = capsys.readouterr().out
    assert "dry run" in out                            # nothing actually left the machine
    assert "intent    interested" in out
    assert "blended CPM        $3.51" in out
    assert '"cost_per_conversion_usd": 1.24' in out

    outbox = os.path.join(run.workspace, "outbox", "d-kilat-c014.eml")
    assert os.path.isfile(outbox)


def test_unsubscribe_reply_blocklists_and_blocks_future_drafts(run, capsys):
    run("brief", SAMPLE_BRIEF, "--id", "kilat")
    run("match", "--campaign", "kilat", "--limit", "3")
    run("draft", "--campaign", "kilat", "--limit", "1")
    run("approve", "d-kilat-c014", "--by", "henggar")
    run("send", "d-kilat-c014")
    capsys.readouterr()

    assert run("reply", "d-kilat-c014", "--text", "no thanks, remove me") == 0
    assert "blocklist" in capsys.readouterr().out
    assert read(run.workspace, "blocklist")[0]["creator_id"] == "c014"

    run("match", "--campaign", "kilat", "--limit", "5")
    matches = {m["creator_id"]: m for m in read(run.workspace, "matches")}
    assert matches["c014"]["excluded"] is True


def test_editing_after_approval_requires_re_approval(run, capsys):
    run("brief", SAMPLE_BRIEF, "--id", "kilat")
    run("match", "--campaign", "kilat", "--limit", "3")
    run("draft", "--campaign", "kilat", "--limit", "1")
    run("approve", "d-kilat-c014", "--by", "henggar")
    body = ("Halo kak, versi yang sudah aku rapikan. #ad "
            "Kalau nggak cocok, bales 'nggak dulu' aja, aku nggak akan kirim lagi.")
    assert run("edit", "d-kilat-c014", "--body", body) == 0
    capsys.readouterr()
    assert run("send", "d-kilat-c014") == 1
    assert "human must approve" in capsys.readouterr().out


def test_receipt_hash_anchor_and_verify(run, capsys):
    run("brief", SAMPLE_BRIEF, "--id", "kilat")
    run("deal", "open", "--campaign", "kilat", "--creator", "c014", "--fee", "260")
    run("deal", "deliverable", "deal-kilat-c014", "--desc", "2 x TikTok", "--due", "2026-10-05")
    capsys.readouterr()

    assert run("receipt", "hash", "--deal", "deal-kilat-c014") == 0
    digest = capsys.readouterr().out.strip()
    assert len(digest) == 64

    assert run("receipt", "anchor", "--deal", "deal-kilat-c014") == 0
    assert "not anchored" in capsys.readouterr().out      # no devnet keypair configured here

    assert run("receipt", "verify", "--deal", "deal-kilat-c014") == 0
    assert "terms are unchanged" in capsys.readouterr().out

    # change the agreed terms, and the receipt stops matching
    run("deal", "deliverable", "deal-kilat-c014", "--desc", "1 x YouTube", "--due", "2026-10-12")
    capsys.readouterr()
    assert run("receipt", "verify", "--deal", "deal-kilat-c014") == 2
    assert "the terms changed" in capsys.readouterr().out


def test_unknown_campaign_is_refused_cleanly(run, capsys):
    assert run("match", "--campaign", "ghost") == 1
    assert "refused:" in capsys.readouterr().out

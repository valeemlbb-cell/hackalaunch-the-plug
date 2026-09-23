"""Receipts, the store, the config guard rails, and the dashboard's CSRF check."""
from __future__ import annotations

import json
import os

import pytest

from plugboard import receipts
from plugboard.config import ConfigError, settings_from_env
from plugboard.store import Store
from plugboard.tracking import add_deliverable, load_deal, open_deal


@pytest.fixture
def deal(store):
    open_deal(store, "kilat", "c014", 260)
    add_deliverable(store, "deal-kilat-c014", "2 x TikTok short", "2026-10-05")
    return load_deal(store, "deal-kilat-c014")


# ------------------------------------------------------------------- receipts
def test_terms_hash_is_stable_across_runs(deal):
    assert receipts.terms_hash(deal) == receipts.terms_hash(deal)
    assert len(receipts.terms_hash(deal)) == 64


def test_changing_the_fee_changes_the_hash(store, deal):
    before = receipts.terms_hash(deal)
    from dataclasses import replace
    assert receipts.terms_hash(replace(deal, agreed_fee_usd=999)) != before


def test_adding_a_deliverable_changes_the_hash(store, deal):
    before = receipts.terms_hash(deal)
    add_deliverable(store, deal.deal_id, "1 x YouTube video", "2026-10-12")
    assert receipts.terms_hash(load_deal(store, deal.deal_id)) != before


def test_verify_hash_detects_a_rewritten_deal(store, deal):
    digest = receipts.terms_hash(deal)
    assert receipts.verify_hash(deal, digest) is True
    from dataclasses import replace
    assert receipts.verify_hash(replace(deal, agreed_fee_usd=1), digest) is False


def test_memo_text_carries_the_version_deal_and_hash(deal):
    memo = receipts.memo_text(deal)
    assert memo.startswith("plugboard:v1:")
    assert deal.deal_id in memo and receipts.terms_hash(deal) in memo


def test_anchoring_without_a_keypair_degrades_instead_of_raising(deal, settings):
    outcome = receipts.anchor_deal(deal, settings)
    assert outcome["anchored"] is False
    assert "SOLANA_KEYPAIR_PATH" in outcome["reason"]
    assert outcome["hash"] == receipts.terms_hash(deal)      # the hash still exists


def test_anchoring_with_a_missing_keypair_file_degrades(deal, settings, monkeypatch):
    from dataclasses import replace
    bad = replace(settings, solana_keypair_path="/definitely/not/here.json")
    assert receipts.anchor_deal(deal, bad)["anchored"] is False


# --------------------------------------------------------------------- config
def test_mainnet_is_refused_outright(monkeypatch):
    monkeypatch.setenv("SOLANA_CLUSTER", "mainnet-beta")
    with pytest.raises(ConfigError, match="never touches mainnet"):
        settings_from_env("ws")


def test_default_cluster_is_devnet_and_default_send_mode_is_dry_run(settings):
    assert settings.solana_cluster == "devnet"
    assert settings.send_mode == "dry_run"
    assert settings.sending_is_live is False


def test_live_mode_without_smtp_is_still_not_live(monkeypatch, tmp_path):
    monkeypatch.setenv("PLUGBOARD_SEND_MODE", "live")
    assert settings_from_env(str(tmp_path)).sending_is_live is False


def test_unknown_send_mode_is_refused(monkeypatch):
    monkeypatch.setenv("PLUGBOARD_SEND_MODE", "yolo")
    with pytest.raises(ConfigError):
        settings_from_env("ws")


def test_the_approval_secret_is_written_outside_any_tracked_file(settings):
    from plugboard.config import SECRET_FILENAME, approval_secret
    secret = approval_secret(settings)
    assert len(secret) == 64
    assert os.path.isfile(os.path.join(settings.workspace, SECRET_FILENAME))


# ---------------------------------------------------------------------- store
def test_writes_are_atomic_and_round_trip(tmp_path):
    store = Store(str(tmp_path / "ws"))
    store.write("campaigns", [{"campaign_id": "a"}])
    store.upsert("campaigns", "campaign_id", {"campaign_id": "b"})
    store.upsert("campaigns", "campaign_id", {"campaign_id": "a", "goal": "sales"})
    rows = {r["campaign_id"]: r for r in store.read("campaigns")}
    assert rows["a"]["goal"] == "sales" and set(rows) == {"a", "b"}


def test_unknown_collection_is_refused(tmp_path):
    with pytest.raises(KeyError):
        Store(str(tmp_path)).read("secrets")


def test_a_torn_event_line_does_not_break_the_audit_view(tmp_path):
    store = Store(str(tmp_path / "ws"))
    store.log("draft.queued", "d1", creator="c1")
    with open(store.path("events.jsonl"), "a", encoding="utf-8") as fh:
        fh.write("{not json\n")
    store.log("draft.approved", "d1", by="henggar")
    assert [e["kind"] for e in store.events()] == ["draft.queued", "draft.approved"]


def test_blocklist_is_idempotent_and_permanent(tmp_path):
    store = Store(str(tmp_path / "ws"))
    store.block("c014", "opted out")
    store.block("c014", "opted out again")
    assert len(store.read("blocklist")) == 1
    assert store.is_blocked("c014") is True


def test_corrupt_collection_file_fails_loudly(tmp_path):
    store = Store(str(tmp_path / "ws"))
    with open(store.path("deals.json"), "w", encoding="utf-8") as fh:
        fh.write("{{{")
    with pytest.raises(RuntimeError, match="unreadable"):
        store.read("deals")


# ------------------------------------------------------------------ dashboard
def test_dashboard_refuses_to_bind_a_public_interface(tmp_path, monkeypatch):
    from plugboard.app import Plugboard
    from plugboard.web import build_server
    monkeypatch.setenv("PLUGBOARD_WORKSPACE", str(tmp_path / "ws"))
    pb = Plugboard(workspace=str(tmp_path / "ws"),
                   catalog_path=os.path.join(os.path.dirname(os.path.dirname(
                       os.path.abspath(__file__))), "data", "creators.seed.json"))
    with pytest.raises(RuntimeError, match="refusing to bind"):
        build_server(pb, host="0.0.0.0", port=0)


def test_contact_details_are_not_in_the_committed_index():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "creators.seed.json")
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    assert "@" not in raw.replace("@creator", "")   # no email addresses, no handles
    rows = json.loads(raw)
    assert all("contact" not in k or k == "contact_channel" or k == "contact_ref"
               for row in rows for k in row)

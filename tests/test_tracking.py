"""Stage 4: deals, deadlines, and numbers that have to trace back to a URL."""
from __future__ import annotations

import pytest

from plugboard.tracking import (TrackingError, add_deliverable, campaign_summary, due_soon,
                                load_deal, mark_deliverable, open_deal, record_result, set_status)


@pytest.fixture
def deal(store):
    open_deal(store, "kilat", "c014", 260)
    set_status(store, "deal-kilat-c014", "agreed")
    add_deliverable(store, "deal-kilat-c014", "2 x TikTok short", "2026-10-05")
    add_deliverable(store, "deal-kilat-c014", "1 x YouTube video", "2026-10-12")
    return load_deal(store, "deal-kilat-c014")


def test_a_new_deal_starts_in_negotiating(store):
    assert open_deal(store, "kilat", "c002", 300).status == "negotiating"


def test_status_only_moves_along_the_declared_path(store, deal):
    set_status(store, deal.deal_id, "running")
    set_status(store, deal.deal_id, "completed")
    with pytest.raises(TrackingError, match="can only move to"):
        set_status(store, deal.deal_id, "negotiating")


def test_illegal_jump_is_refused(store):
    open_deal(store, "kilat", "c020", 80)
    with pytest.raises(TrackingError):
        set_status(store, "deal-kilat-c020", "completed")


def test_deliverable_needs_an_iso_date(store, deal):
    with pytest.raises(TrackingError, match="YYYY-MM-DD"):
        add_deliverable(store, deal.deal_id, "1 x story", "next tuesday")


def test_result_without_a_url_is_refused(store, deal):
    with pytest.raises(TrackingError, match="public URL"):
        record_result(store, deal.deal_id, deal.deliverables[0].deliverable_id, "tiktok", "")


def test_result_for_an_unknown_deliverable_is_refused(store, deal):
    with pytest.raises(TrackingError, match="no deliverable"):
        record_result(store, deal.deal_id, "nope", "tiktok", "https://example.invalid/1", views=1)


def test_cpm_is_derived_from_recorded_views_not_typed_in(store, deal):
    updated = record_result(store, deal.deal_id, deal.deliverables[0].deliverable_id,
                            "tiktok", "https://example.invalid/1", views=52_000)
    assert updated.total_views() == 52_000
    assert updated.actual_cpm() == round(260 / 52.0, 2)


def test_recording_the_same_url_twice_updates_rather_than_double_counts(store, deal):
    item = deal.deliverables[0].deliverable_id
    record_result(store, deal.deal_id, item, "tiktok", "https://example.invalid/1", views=10_000)
    updated = record_result(store, deal.deal_id, item, "tiktok", "https://example.invalid/1",
                            views=41_000)
    assert updated.total_views() == 41_000
    assert len(updated.results) == 1


def test_due_soon_flags_overdue_items_first(store, deal):
    rows = due_soon(store, within_days=30, as_of="2026-10-08")
    assert rows[0]["deliverable_id"].endswith("d1")
    assert rows[0]["overdue"] is True
    assert rows[1]["overdue"] is False


def test_delivered_items_drop_out_of_the_due_list(store, deal):
    mark_deliverable(store, deal.deal_id, deal.deliverables[0].deliverable_id, "live",
                     "https://example.invalid/1")
    rows = due_soon(store, within_days=30, as_of="2026-10-08")
    assert all(not r["deliverable_id"].endswith("d1") for r in rows)


def test_unknown_deliverable_state_is_refused(store, deal):
    with pytest.raises(TrackingError, match="unknown deliverable status"):
        mark_deliverable(store, deal.deal_id, deal.deliverables[0].deliverable_id, "vibes")


def test_campaign_summary_reports_spend_reach_and_delivery(store, deal):
    item = deal.deliverables[0].deliverable_id
    mark_deliverable(store, deal.deal_id, item, "live", "https://example.invalid/1")
    record_result(store, deal.deal_id, item, "tiktok", "https://example.invalid/1",
                  views=74_000, clicks=1_900, conversions=210)
    summary = campaign_summary(store, "kilat")
    assert summary["committed_usd"] == 260
    assert summary["views"] == 74_000
    assert summary["conversions"] == 210
    assert summary["blended_cpm_usd"] == round(260 / 74.0, 2)
    assert summary["cost_per_conversion_usd"] == round(260 / 210, 2)
    assert summary["deliverables_done"] == 1 and summary["deliverables_total"] == 2
    assert summary["delivery_rate"] == 0.5


def test_summary_of_an_empty_campaign_is_all_zeros_not_a_crash(store):
    summary = campaign_summary(store, "nothing-here")
    assert summary["deals"] == 0 and summary["blended_cpm_usd"] == 0.0

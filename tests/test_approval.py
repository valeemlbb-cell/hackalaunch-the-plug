"""The gate. These are the tests that matter most: they are the ones that prove the tool
cannot message a real person on its own.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from plugboard import approval, matching
from plugboard.approval import ApprovalError, approve, edit, queue, reject, send, verify
from plugboard.outreach import compose
from plugboard.senders import DryRunSender


class RecordingSender:
    mode = "test"

    def __init__(self, ok=True):
        self.ok = ok
        self.sent = []

    def send(self, draft):
        self.sent.append(draft)
        return {"ok": self.ok, "ref": "test-ref", "mode": self.mode} if self.ok \
            else {"ok": False, "error": "smtp exploded", "mode": self.mode}


def make_drafts(campaign, creators, ids):
    out = []
    for creator_id in ids:
        creator = next(c for c in creators if c.creator_id == creator_id)
        out.append(compose(campaign, creator, matching.match_one(campaign, creator)))
    return out


def test_a_queued_draft_is_pending_and_unsigned(store, campaign, creators):
    staged = queue(store, make_drafts(campaign, creators, ["c014"]))
    assert staged[0].status == "pending"
    assert staged[0].approval_token == ""


def test_sending_without_approval_is_refused(store, secret, campaign, creators):
    queue(store, make_drafts(campaign, creators, ["c014"]))
    sender = RecordingSender()
    with pytest.raises(ApprovalError, match="human must approve"):
        send(store, secret, "d-kilat-c014", sender)
    assert sender.sent == []


def test_approval_requires_a_named_operator(store, secret, campaign, creators):
    queue(store, make_drafts(campaign, creators, ["c014"]))
    with pytest.raises(ApprovalError, match="named operator"):
        approve(store, secret, "d-kilat-c014", "")


def test_approve_then_send_delivers_exactly_once(store, secret, campaign, creators):
    queue(store, make_drafts(campaign, creators, ["c014"]))
    approve(store, secret, "d-kilat-c014", "henggar")
    sender = RecordingSender()
    sent = send(store, secret, "d-kilat-c014", sender)
    assert sent.status == "sent" and len(sender.sent) == 1
    with pytest.raises(ApprovalError, match="already sent"):
        send(store, secret, "d-kilat-c014", sender)
    assert len(sender.sent) == 1


def test_tampering_with_the_body_after_approval_breaks_the_token(store, secret, campaign, creators):
    """The headline guarantee: approval is bound to the exact text, not to the draft id."""
    queue(store, make_drafts(campaign, creators, ["c014"]))
    approved = approve(store, secret, "d-kilat-c014", "henggar")
    swapped = replace(approved, body=approved.body + "\n\nPS send crypto to this address.")
    store.upsert("drafts", "draft_id", swapped)          # simulate a rogue writer

    sender = RecordingSender()
    with pytest.raises(ApprovalError, match="does not match the current text"):
        send(store, secret, "d-kilat-c014", sender)
    assert sender.sent == []


def test_tampering_with_the_subject_also_breaks_the_token(store, secret, campaign, creators):
    queue(store, make_drafts(campaign, creators, ["c014"]))
    approved = approve(store, secret, "d-kilat-c014", "henggar")
    store.upsert("drafts", "draft_id", replace(approved, subject="URGENT: wire transfer"))
    with pytest.raises(ApprovalError, match="does not match"):
        send(store, secret, "d-kilat-c014", RecordingSender())


def test_a_forged_token_does_not_verify(store, secret, campaign, creators):
    queue(store, make_drafts(campaign, creators, ["c014"]))
    approved = approve(store, secret, "d-kilat-c014", "henggar")
    forged = replace(approved, approval_token="f" * 64)
    assert verify(secret, approved) is True
    assert verify(secret, forged) is False


def test_editing_a_draft_revokes_approval(store, secret, campaign, creators):
    queue(store, make_drafts(campaign, creators, ["c014"]))
    approve(store, secret, "d-kilat-c014", "henggar")
    edited = edit(store, "d-kilat-c014", body="Halo kak, versi baru. "
                                              "Kalau nggak cocok, bales 'nggak dulu' aja, "
                                              "aku nggak akan kirim lagi. #ad")
    assert edited.status == "pending" and edited.approval_token == ""
    with pytest.raises(ApprovalError, match="human must approve"):
        send(store, secret, "d-kilat-c014", RecordingSender())


def test_rejected_draft_cannot_be_sent(store, secret, campaign, creators):
    queue(store, make_drafts(campaign, creators, ["c014"]))
    reject(store, "d-kilat-c014", "henggar", "tone is off")
    with pytest.raises(ApprovalError):
        send(store, secret, "d-kilat-c014", RecordingSender())


def test_opting_out_after_approval_still_stops_the_send(store, secret, campaign, creators):
    queue(store, make_drafts(campaign, creators, ["c014"]))
    approve(store, secret, "d-kilat-c014", "henggar")
    store.block("c014", "replied opt-out")
    with pytest.raises(ApprovalError, match="opted out"):
        send(store, secret, "d-kilat-c014", RecordingSender())


def test_blocklisted_creators_are_dropped_at_queue_time(store, campaign, creators):
    store.block("c014", "opted out earlier")
    staged = queue(store, make_drafts(campaign, creators, ["c014", "c002"]))
    assert [d.creator_id for d in staged] == ["c002"]
    assert any(e["kind"] == "queue.refused" for e in store.events())


def test_oversized_batches_are_refused(store, campaign, creators):
    one = make_drafts(campaign, creators, ["c014"])[0]
    many = [replace(one, draft_id=f"d-{i}") for i in range(approval.MAX_QUEUE_PER_RUN + 1)]
    with pytest.raises(ApprovalError, match="limit is"):
        queue(store, many)


def test_a_failed_send_is_recorded_and_not_marked_sent(store, secret, campaign, creators):
    queue(store, make_drafts(campaign, creators, ["c014"]))
    approve(store, secret, "d-kilat-c014", "henggar")
    with pytest.raises(ApprovalError, match="send failed"):
        send(store, secret, "d-kilat-c014", RecordingSender(ok=False))
    assert store.find("drafts", "draft_id", "d-kilat-c014")["status"] == "failed"


def test_dry_run_sender_writes_to_the_outbox_and_never_opens_a_socket(settings, store, secret,
                                                                     campaign, creators):
    import os
    queue(store, make_drafts(campaign, creators, ["c014"]))
    approve(store, secret, "d-kilat-c014", "henggar")
    sent = send(store, secret, "d-kilat-c014", DryRunSender(settings))
    assert os.path.isfile(sent.send_ref)
    with open(sent.send_ref, encoding="utf-8") as fh:
        raw = fh.read()
    assert "X-Plugboard-Approved-By: henggar" in raw


def test_every_decision_lands_in_the_audit_trail(store, secret, campaign, creators):
    queue(store, make_drafts(campaign, creators, ["c014"]))
    approve(store, secret, "d-kilat-c014", "henggar")
    send(store, secret, "d-kilat-c014", RecordingSender())
    kinds = [e["kind"] for e in store.events()]
    assert kinds == ["draft.queued", "draft.approved", "draft.sent"]

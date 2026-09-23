"""Stage 3b - the human gate. Nothing reaches a real creator without a person saying yes
to that exact text.

How it is enforced, rather than merely promised:

  approve()  signs HMAC(workspace secret, draft_id + body_hash) and stores it on the draft.
  send()     recomputes body_hash from the body it is about to send, recomputes the HMAC,
             and compares. If either the body or the subject changed by a single character
             after approval, the token no longer verifies and the send is refused.

So "approve a polite message, then swap in something else" - by a bug, a prompt injection
in a creator's reply, or a careless edit - fails closed. The agent can draft all day; it
cannot manufacture a token, because the secret lives outside the repo and outside the
model's reach.

Queue limits here are a second seatbelt, not the main one: one approval per message means
bulk unsolicited messaging is not a thing this tool can do at speed.
"""
from __future__ import annotations

import hmac
import time
from dataclasses import replace
from hashlib import sha256

from .config import DAILY_SEND_CAP, MIN_SECONDS_BETWEEN_SENDS, RETOUCH_COOLDOWN_DAYS
from .models import Draft, content_hash
from .store import Store, utc_now

MAX_QUEUE_PER_RUN = 10   # a single `queue` call may never stage more than this


class ApprovalError(RuntimeError):
    """Refused. Always safe to show the operator verbatim."""


def body_hash_of(draft: Draft) -> str:
    return content_hash({"subject": draft.subject, "body": draft.body})


def sign(secret: bytes, draft: Draft) -> str:
    payload = f"{draft.draft_id}:{body_hash_of(draft)}".encode("utf-8")
    return hmac.new(secret, payload, sha256).hexdigest()


def verify(secret: bytes, draft: Draft) -> bool:
    if not draft.approval_token:
        return False
    return hmac.compare_digest(draft.approval_token, sign(secret, draft))


# --------------------------------------------------------------------- queue
def queue(store: Store, drafts: list) -> list:
    """Stage drafts as `pending`. Refuses oversized batches and repeat contacts."""
    if len(drafts) > MAX_QUEUE_PER_RUN:
        raise ApprovalError(
            f"{len(drafts)} drafts in one queue call, limit is {MAX_QUEUE_PER_RUN}. "
            "Plugboard stages small batches on purpose - every message is approved individually.")
    blocked = store.blocked_ids()
    existing = store.read("drafts")
    recent = _recently_contacted(existing)
    staged = []
    for draft in drafts:
        if draft.creator_id in blocked:
            store.log("queue.refused", draft.draft_id, reason="blocklisted", creator=draft.creator_id)
            continue
        if draft.creator_id in recent:
            store.log("queue.refused", draft.draft_id, reason="cooldown", creator=draft.creator_id)
            continue
        pending = replace(draft, status="pending", body_hash=body_hash_of(draft), created_at=utc_now())
        store.upsert("drafts", "draft_id", pending)
        store.log("draft.queued", pending.draft_id, creator=pending.creator_id,
                  campaign=pending.campaign_id, channel=pending.channel)
        staged.append(pending)
    return staged


def _recently_contacted(rows: list) -> set:
    """Creator ids messaged inside the cooldown window."""
    cutoff = time.time() - RETOUCH_COOLDOWN_DAYS * 86400
    out = set()
    for row in rows:
        if row.get("status") != "sent" or not row.get("sent_at"):
            continue
        stamp = _epoch(row["sent_at"])
        if stamp and stamp > cutoff:
            out.add(row.get("creator_id"))
    return out


def _epoch(stamp: str):
    try:
        return time.mktime(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ"))
    except (ValueError, TypeError):
        return None


# ------------------------------------------------------------------ decisions
def approve(store: Store, secret: bytes, draft_id: str, operator: str) -> Draft:
    if not operator:
        raise ApprovalError("approval needs a named operator - set PLUGBOARD_OPERATOR or pass --by")
    draft = _load(store, draft_id)
    if draft.status not in ("pending", "rejected"):
        raise ApprovalError(f"draft {draft_id} is {draft.status}, only pending drafts can be approved")
    approved = replace(draft, status="approved", body_hash=body_hash_of(draft),
                       approved_by=operator, approved_at=utc_now(), rejected_reason="")
    approved = replace(approved, approval_token=sign(secret, approved))
    store.upsert("drafts", "draft_id", approved)
    store.log("draft.approved", draft_id, by=operator, creator=approved.creator_id,
              body_hash=approved.body_hash)
    return approved


def reject(store: Store, draft_id: str, operator: str, reason: str = "") -> Draft:
    draft = _load(store, draft_id)
    rejected = replace(draft, status="rejected", approval_token="", approved_by="",
                       approved_at="", rejected_reason=reason or "no reason given")
    store.upsert("drafts", "draft_id", rejected)
    store.log("draft.rejected", draft_id, by=operator, reason=rejected.rejected_reason)
    return rejected


def edit(store: Store, draft_id: str, *, subject: str = None, body: str = None) -> Draft:
    """Editing always revokes approval - the token is bound to the old text."""
    draft = _load(store, draft_id)
    changed = replace(draft,
                      subject=draft.subject if subject is None else subject,
                      body=draft.body if body is None else body)
    changed = replace(changed, status="pending", approval_token="", approved_by="", approved_at="",
                      body_hash=body_hash_of(changed))
    store.upsert("drafts", "draft_id", changed)
    store.log("draft.edited", draft_id, body_hash=changed.body_hash)
    return changed


# ---------------------------------------------------------------------- send
def send(store: Store, secret: bytes, draft_id: str, sender) -> Draft:
    """Send one approved draft. Every refusal below is deliberate."""
    draft = _load(store, draft_id)
    if draft.status == "sent":
        raise ApprovalError(f"draft {draft_id} was already sent at {draft.sent_at}")
    if draft.status != "approved":
        raise ApprovalError(f"draft {draft_id} is {draft.status}; a human must approve it first")
    if not verify(secret, draft):
        raise ApprovalError(
            f"approval token for {draft_id} does not match the current text. The message changed "
            "after it was approved - re-approve it before sending.")
    if store.is_blocked(draft.creator_id):
        raise ApprovalError(f"{draft.creator_id} opted out after approval - send refused")
    _check_rate(store)

    outcome = sender.send(draft)
    if not outcome.get("ok"):
        failed = replace(draft, status="failed", send_ref=str(outcome.get("error", "")))
        store.upsert("drafts", "draft_id", failed)
        store.log("draft.send_failed", draft_id, error=failed.send_ref)
        raise ApprovalError(f"send failed for {draft_id}: {failed.send_ref}")

    sent = replace(draft, status="sent", sent_at=utc_now(), send_ref=str(outcome.get("ref", "")))
    store.upsert("drafts", "draft_id", sent)
    store.log("draft.sent", draft_id, creator=sent.creator_id, channel=sent.channel,
              mode=outcome.get("mode", "unknown"), send_ref=sent.send_ref)
    return sent


def _check_rate(store: Store) -> None:
    rows = [r for r in store.read("drafts") if r.get("status") == "sent" and r.get("sent_at")]
    day = utc_now()[:10]
    today_count = sum(1 for r in rows if str(r.get("sent_at", ""))[:10] == day)
    if today_count >= DAILY_SEND_CAP:
        raise ApprovalError(f"daily send cap reached ({DAILY_SEND_CAP} today). Nothing else goes out until tomorrow.")
    stamps = [s for s in (_epoch(r["sent_at"]) for r in rows) if s]
    if stamps:
        gap = time.time() - max(stamps)
        if gap < MIN_SECONDS_BETWEEN_SENDS:
            raise ApprovalError(
                f"last send was {int(gap)}s ago; Plugboard waits {MIN_SECONDS_BETWEEN_SENDS}s between messages")


def _load(store: Store, draft_id: str) -> Draft:
    row = store.find("drafts", "draft_id", draft_id)
    if not row:
        raise ApprovalError(f"no draft with id {draft_id!r}")
    known = {f for f in Draft.__dataclass_fields__}
    return Draft(**{k: v for k, v in row.items() if k in known})

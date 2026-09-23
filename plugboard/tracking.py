"""Stage 4 - what was agreed, what is due, what it actually did.

A Deal is the object a founder cares about after the handshake: a fee, a list of
deliverables with dates, and the numbers each one produced. Status only moves forward
through a declared table, so a "completed" deal cannot quietly slide back to
"negotiating" because some code path forgot.

Reported numbers are always labelled with where they came from (`manual` or `api`) and
recomputed CPM is derived, never typed in - the brief disqualifies fake engagement
metrics, so a figure nobody can trace back to a URL does not get to look official.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta

from .models import Deal, Deliverable, Result
from .store import Store, today, utc_now

ALLOWED_TRANSITIONS = {
    "negotiating": ("agreed", "cancelled"),
    "agreed": ("running", "cancelled"),
    "running": ("completed", "cancelled"),
    "completed": (),
    "cancelled": (),
}
DELIVERABLE_STATES = ("agreed", "in_progress", "delivered", "live", "missed")
OPEN_STATES = ("agreed", "in_progress")


class TrackingError(RuntimeError):
    pass


def _to_deal(row: dict) -> Deal:
    deliverables = tuple(Deliverable(**{k: v for k, v in d.items()
                                        if k in Deliverable.__dataclass_fields__})
                         for d in row.get("deliverables", ()) or ())
    results = tuple(Result(**{k: v for k, v in r.items() if k in Result.__dataclass_fields__})
                    for r in row.get("results", ()) or ())
    known = {k: v for k, v in row.items()
             if k in Deal.__dataclass_fields__ and k not in ("deliverables", "results")}
    return Deal(deliverables=deliverables, results=results, **known)


def load_deal(store: Store, deal_id: str) -> Deal:
    row = store.find("deals", "deal_id", deal_id)
    if not row:
        raise TrackingError(f"no deal with id {deal_id!r}")
    return _to_deal(row)


def all_deals(store: Store) -> list:
    return [_to_deal(r) for r in store.read("deals")]


def open_deal(store: Store, campaign_id: str, creator_id: str, fee_usd: int,
              deal_id: str = "") -> Deal:
    deal = Deal(
        deal_id=deal_id or f"deal-{campaign_id}-{creator_id}",
        campaign_id=campaign_id,
        creator_id=creator_id,
        status="negotiating",
        agreed_fee_usd=int(fee_usd or 0),
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    store.upsert("deals", "deal_id", deal)
    store.log("deal.opened", deal.deal_id, creator=creator_id, campaign=campaign_id, fee_usd=deal.agreed_fee_usd)
    return deal


def set_status(store: Store, deal_id: str, status: str) -> Deal:
    deal = load_deal(store, deal_id)
    if status == deal.status:
        return deal
    allowed = ALLOWED_TRANSITIONS.get(deal.status, ())
    if status not in allowed:
        raise TrackingError(
            f"deal {deal_id} is {deal.status}; it can only move to {', '.join(allowed) or 'nothing'}, not {status!r}")
    moved = replace(deal, status=status, updated_at=utc_now())
    store.upsert("deals", "deal_id", moved)
    store.log("deal.status", deal_id, was=deal.status, now=status)
    return moved


def add_deliverable(store: Store, deal_id: str, description: str, due_on: str,
                    deliverable_id: str = "") -> Deal:
    deal = load_deal(store, deal_id)
    _check_date(due_on)
    item = Deliverable(
        deliverable_id=deliverable_id or f"{deal_id}-d{len(deal.deliverables) + 1}",
        description=description,
        due_on=due_on,
    )
    updated = replace(deal, deliverables=deal.deliverables + (item,), updated_at=utc_now())
    store.upsert("deals", "deal_id", updated)
    store.log("deliverable.added", item.deliverable_id, deal=deal_id, due_on=due_on)
    return updated


def mark_deliverable(store: Store, deal_id: str, deliverable_id: str, status: str,
                     proof_url: str = "") -> Deal:
    if status not in DELIVERABLE_STATES:
        raise TrackingError(f"unknown deliverable status {status!r}; expected one of {DELIVERABLE_STATES}")
    deal = load_deal(store, deal_id)
    found = False
    items = []
    for item in deal.deliverables:
        if item.deliverable_id == deliverable_id:
            found = True
            stamp = utc_now() if status in ("delivered", "live") else item.delivered_at
            items.append(replace(item, status=status, proof_url=proof_url or item.proof_url,
                                 delivered_at=stamp))
        else:
            items.append(item)
    if not found:
        raise TrackingError(f"deal {deal_id} has no deliverable {deliverable_id!r}")
    updated = replace(deal, deliverables=tuple(items), updated_at=utc_now())
    store.upsert("deals", "deal_id", updated)
    store.log("deliverable.status", deliverable_id, deal=deal_id, now=status, proof=proof_url)
    return updated


def record_result(store: Store, deal_id: str, deliverable_id: str, platform: str, url: str,
                  *, views: int = 0, likes: int = 0, comments: int = 0, shares: int = 0,
                  clicks: int = 0, conversions: int = 0, source: str = "manual") -> Deal:
    """Attach measured numbers to a deliverable. A result always carries a URL."""
    if not url:
        raise TrackingError("a result needs the public URL of the post it measures")
    deal = load_deal(store, deal_id)
    if deliverable_id not in {d.deliverable_id for d in deal.deliverables}:
        raise TrackingError(f"deal {deal_id} has no deliverable {deliverable_id!r}")
    result = Result(deliverable_id=deliverable_id, platform=platform, url=url, views=int(views),
                    likes=int(likes), comments=int(comments), shares=int(shares), clicks=int(clicks),
                    conversions=int(conversions), source=source, recorded_at=utc_now())
    kept = tuple(r for r in deal.results if not (r.deliverable_id == deliverable_id and r.url == url))
    updated = replace(deal, results=kept + (result,), updated_at=utc_now())
    store.upsert("deals", "deal_id", updated)
    store.log("result.recorded", deliverable_id, deal=deal_id, platform=platform, views=int(views), source=source)
    return updated


def _check_date(value: str) -> None:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except (ValueError, TypeError):
        raise TrackingError(f"due date {value!r} is not YYYY-MM-DD") from None


def due_soon(store: Store, within_days: int = 3, as_of: str = "") -> list:
    """Deliverables that are overdue or land inside the window. Sorted, most urgent first."""
    reference = datetime.strptime(as_of or today(), "%Y-%m-%d").date()
    horizon = reference + timedelta(days=within_days)
    rows = []
    for deal in all_deals(store):
        if deal.status in ("cancelled", "completed"):
            continue
        for item in deal.deliverables:
            if item.status not in OPEN_STATES:
                continue
            try:
                due = datetime.strptime(item.due_on, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                continue
            if due <= horizon:
                rows.append({
                    "deal_id": deal.deal_id,
                    "creator_id": deal.creator_id,
                    "deliverable_id": item.deliverable_id,
                    "description": item.description,
                    "due_on": item.due_on,
                    "days_left": (due - reference).days,
                    "overdue": due < reference,
                    "status": item.status,
                })
    rows.sort(key=lambda r: (r["days_left"], r["deal_id"]))
    return rows


def campaign_summary(store: Store, campaign_id: str) -> dict:
    """One row per campaign: spend, reach, blended CPM, delivery rate."""
    deals = [d for d in all_deals(store) if d.campaign_id == campaign_id]
    live = [d for d in deals if d.status in ("agreed", "running", "completed")]
    spend = sum(d.agreed_fee_usd for d in live)
    views = sum(d.total_views() for d in deals)
    clicks = sum(r.clicks for d in deals for r in d.results)
    conversions = sum(r.conversions for d in deals for r in d.results)
    items = [i for d in deals for i in d.deliverables]
    delivered = [i for i in items if i.status in ("delivered", "live")]
    missed = [i for i in items if i.status == "missed"]
    return {
        "campaign_id": campaign_id,
        "deals": len(deals),
        "deals_live": len(live),
        "committed_usd": spend,
        "views": views,
        "clicks": clicks,
        "conversions": conversions,
        "blended_cpm_usd": round(spend / (views / 1000.0), 2) if views else 0.0,
        "cost_per_conversion_usd": round(spend / conversions, 2) if conversions else 0.0,
        "deliverables_total": len(items),
        "deliverables_done": len(delivered),
        "deliverables_missed": len(missed),
        "delivery_rate": round(len(delivered) / len(items), 3) if items else 0.0,
        "as_of": utc_now(),
    }

"""Immutable records that move through the Plugboard loop.

Every stage produces a new frozen record instead of mutating the previous one, so a
campaign's history is an append-only trail: Brief -> Campaign -> Match -> Draft ->
Approval -> Deal -> Result. `replace()` from dataclasses is the only way to "change"
anything, and it always returns a copy.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1


def _canonical(payload: Any) -> str:
    """Stable JSON text for hashing: sorted keys, no whitespace jitter, UTF-8 preserved."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(payload: Any) -> str:
    """sha256 of the canonical form. Same input -> same hash on every machine."""
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def as_dict(record: Any) -> dict:
    """Dataclass -> plain dict (recursively), safe to json.dump."""
    if dataclasses.is_dataclass(record) and not isinstance(record, type):
        return {k: as_dict(v) for k, v in dataclasses.asdict(record).items()}
    if isinstance(record, dict):
        return {k: as_dict(v) for k, v in record.items()}
    if isinstance(record, (list, tuple)):
        return [as_dict(v) for v in record]
    return record


@dataclass(frozen=True)
class Evidence:
    """One verifiable fact about a creator, with where it came from and when."""
    fact: str
    source_url: str = ""
    observed_at: str = ""

    def line(self) -> str:
        stamp = f" (observed {self.observed_at})" if self.observed_at else ""
        return f"{self.fact}{stamp}"


@dataclass(frozen=True)
class PlatformStats:
    platform: str
    followers: int = 0
    median_views: int = 0
    engagement_rate: float = 0.0      # likes+comments+shares / views, 0..1
    posts_last_30d: int = 0


@dataclass(frozen=True)
class Creator:
    """A creator in the index. No real names, emails or handles live in the seed data."""
    creator_id: str
    display_label: str                 # anonymised, e.g. "ID podcast - personal finance"
    name: str = ""                     # the creator's real name, when the index has one
    languages: tuple = ()
    geo: str = ""
    topics: tuple = ()
    audience_age_band: str = ""        # "18-24", "25-34", "mixed"
    platforms: tuple = ()              # tuple[PlatformStats]
    cadence_per_week: float = 0.0
    days_since_last_post: int = 999
    price_usd_min: int = 0
    price_usd_max: int = 0
    accepts_paid_promo: bool = True
    discloses_ads: bool = True
    contact_channel: str = ""          # "email" | "dm" | "form" - not the address itself
    contact_ref: str = ""              # opaque key resolved from a local, untracked contacts file
    safety_flags: tuple = ()           # e.g. ("gambling_content",)
    evidence: tuple = ()               # tuple[Evidence]

    def stats(self, platform: str):
        for p in self.platforms:
            if p.platform == platform:
                return p
        return None

    def best_platform(self, wanted: tuple = ()):
        pool = [p for p in self.platforms if not wanted or p.platform in wanted]
        if not pool:
            return None
        return max(pool, key=lambda p: p.median_views)


@dataclass(frozen=True)
class Campaign:
    """A founder's brief after it has been turned into something matchable."""
    campaign_id: str
    product: str
    one_liner: str = ""
    goal: str = "awareness"            # awareness | signups | sales | app_installs | community
    languages: tuple = ()
    geo: str = ""
    audience_age_band: str = "mixed"
    interests: tuple = ()
    platforms: tuple = ()
    budget_total_usd: int = 0
    budget_per_creator_usd: int = 0
    target_cpm_usd: float = 0.0        # what the founder is willing to pay per 1k views
    deliverables: tuple = ()
    starts_on: str = ""
    ends_on: str = ""
    kpis: tuple = ()
    tone: str = "direct"
    exclusions: tuple = ()             # safety flags the founder refuses
    is_paid_promotion: bool = True
    raw_brief: str = ""
    warnings: tuple = ()               # what the parser could not find
    created_at: str = ""

    def fingerprint(self) -> str:
        return content_hash(as_dict(self))


@dataclass(frozen=True)
class ScoreLine:
    """One scoring dimension, kept so the UI can show WHY, not just how much."""
    name: str
    weight: float
    score: float                       # 0..1
    reason: str

    @property
    def contribution(self) -> float:
        return round(self.weight * self.score, 4)


@dataclass(frozen=True)
class Match:
    campaign_id: str
    creator_id: str
    score: float
    tier: str                          # A | B | C
    lines: tuple = ()                  # tuple[ScoreLine]
    risks: tuple = ()
    evidence: tuple = ()               # tuple[str] - the facts that drove the score
    suggested_offer_usd: int = 0
    projected_views_low: int = 0
    projected_views_high: int = 0
    excluded: bool = False
    exclusion_reason: str = ""

    def explain(self) -> str:
        head = f"{self.creator_id}  score {self.score:.3f}  tier {self.tier}"
        if self.excluded:
            return f"{head}  EXCLUDED: {self.exclusion_reason}"
        body = "\n".join(
            f"    {l.name:<18} {l.score:.2f} x {l.weight:.2f} = {l.contribution:.3f}  {l.reason}"
            for l in self.lines
        )
        tail = ""
        if self.risks:
            tail = "\n    risks: " + "; ".join(self.risks)
        return f"{head}\n{body}{tail}"


@dataclass(frozen=True)
class Draft:
    """An outreach message that has NOT been sent and cannot be sent without approval."""
    draft_id: str
    campaign_id: str
    creator_id: str
    channel: str
    subject: str
    body: str
    language: str = "en"
    status: str = "pending"            # pending | approved | rejected | sent | failed
    body_hash: str = ""
    approval_token: str = ""
    approved_by: str = ""
    approved_at: str = ""
    rejected_reason: str = ""
    sent_at: str = ""
    send_ref: str = ""
    created_at: str = ""
    kind: str = "first_touch"          # first_touch | reply | followup


@dataclass(frozen=True)
class Deliverable:
    deliverable_id: str
    description: str
    due_on: str
    status: str = "agreed"             # agreed | in_progress | delivered | live | missed
    proof_url: str = ""
    delivered_at: str = ""


@dataclass(frozen=True)
class Result:
    deliverable_id: str
    platform: str
    url: str
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    clicks: int = 0
    conversions: int = 0
    source: str = "manual"             # manual | api
    recorded_at: str = ""


@dataclass(frozen=True)
class Deal:
    deal_id: str
    campaign_id: str
    creator_id: str
    status: str = "negotiating"        # negotiating | agreed | running | completed | cancelled
    agreed_fee_usd: int = 0
    currency: str = "USD"
    deliverables: tuple = ()           # tuple[Deliverable]
    results: tuple = ()                # tuple[Result]
    notes: tuple = ()
    receipt_hash: str = ""
    receipt_signature: str = ""
    receipt_cluster: str = ""
    created_at: str = ""
    updated_at: str = ""

    def total_views(self) -> int:
        return sum(r.views for r in self.results)

    def actual_cpm(self) -> float:
        views = self.total_views()
        if views <= 0 or self.agreed_fee_usd <= 0:
            return 0.0
        return round(self.agreed_fee_usd / (views / 1000.0), 2)


@dataclass(frozen=True)
class Event:
    """Append-only audit line. Nothing side-effecting happens without one of these."""
    at: str
    kind: str
    ref: str
    detail: dict = field(default_factory=dict)

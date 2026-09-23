"""Shared wiring. The CLI and the dashboard both build one of these and nothing else
reaches into config/store/catalog directly.
"""
from __future__ import annotations

import os
from dataclasses import replace

from . import catalog, matching
from .config import Settings, approval_secret, load_dotenv, settings_from_env
from .llm import build_llm
from .models import Campaign, Match, ScoreLine
from .store import Store

DEFAULT_CATALOG = os.path.join("data", "creators.seed.json")


class Plugboard:
    def __init__(self, workspace: str = "", catalog_path: str = "", use_llm: bool = True):
        load_dotenv()
        self.settings: Settings = settings_from_env(workspace)
        self.store = Store(self.settings.workspace)
        self.secret = approval_secret(self.settings)
        self.catalog_path = catalog_path or os.environ.get("PLUGBOARD_CATALOG") or DEFAULT_CATALOG
        self.llm = build_llm(self.settings) if use_llm else None

    # ------------------------------------------------------------- creators
    @property
    def creators(self) -> list:
        if not hasattr(self, "_creators"):
            self._creators = catalog.load_creators(self.catalog_path)
        return self._creators

    def creator(self, creator_id: str):
        for c in self.creators:
            if c.creator_id == creator_id:
                return c
        return None

    def contacts_path(self) -> str:
        return os.path.join(os.path.dirname(os.path.abspath(self.catalog_path)),
                            catalog.CONTACTS_FILENAME)

    def contact_for(self, creator_id: str) -> str:
        creator = self.creator(creator_id)
        return catalog.resolve_contact(creator, self.contacts_path()) if creator else ""

    # ------------------------------------------------------------ campaigns
    def save_campaign(self, campaign: Campaign) -> Campaign:
        self.store.upsert("campaigns", "campaign_id", campaign)
        self.store.log("campaign.saved", campaign.campaign_id, goal=campaign.goal,
                       interests=list(campaign.interests), warnings=list(campaign.warnings))
        return campaign

    def campaign(self, campaign_id: str) -> Campaign:
        row = self.store.find("campaigns", "campaign_id", campaign_id)
        if not row:
            raise KeyError(f"no campaign {campaign_id!r}. Run: plugboard brief <file> --id {campaign_id}")
        known = {k: v for k, v in row.items() if k in Campaign.__dataclass_fields__}
        for field in ("languages", "interests", "platforms", "deliverables", "kpis",
                      "exclusions", "warnings"):
            if field in known:
                known[field] = tuple(known[field] or ())
        return Campaign(**known)

    def campaigns(self) -> list:
        return [self.campaign(r["campaign_id"]) for r in self.store.read("campaigns")]

    # -------------------------------------------------------------- matches
    def run_matching(self, campaign: Campaign, limit: int = 0, diversify: bool = True) -> list:
        ranked = matching.rank(campaign, self.creators, self.store.blocked_ids())
        if limit and diversify:
            top = matching.diversify(ranked, self.creators, limit)
        elif limit:
            top = [m for m in ranked if not m.excluded][:limit]
        else:
            top = ranked
        rows = [self._match_row(m) for m in ranked]
        kept = [r for r in self.store.read("matches") if r.get("campaign_id") != campaign.campaign_id]
        self.store.write("matches", kept + rows)
        self.store.log("match.ran", campaign.campaign_id, scored=len(ranked),
                       excluded=sum(1 for m in ranked if m.excluded), selected=len(top))
        return top

    @staticmethod
    def _match_row(match: Match) -> dict:
        return {
            "campaign_id": match.campaign_id,
            "creator_id": match.creator_id,
            "score": match.score,
            "tier": match.tier,
            "excluded": match.excluded,
            "exclusion_reason": match.exclusion_reason,
            "risks": list(match.risks),
            "evidence": list(match.evidence),
            "suggested_offer_usd": match.suggested_offer_usd,
            "projected_views_low": match.projected_views_low,
            "projected_views_high": match.projected_views_high,
            "lines": [{"name": l.name, "weight": l.weight, "score": l.score,
                       "reason": l.reason, "contribution": l.contribution} for l in match.lines],
        }

    def stored_matches(self, campaign_id: str) -> list:
        rows = [r for r in self.store.read("matches") if r.get("campaign_id") == campaign_id]
        rows.sort(key=lambda r: (r.get("excluded", False), -float(r.get("score", 0))))
        return [self._row_to_match(r) for r in rows]

    @staticmethod
    def _row_to_match(row: dict) -> Match:
        lines = tuple(ScoreLine(name=l["name"], weight=float(l["weight"]),
                                score=float(l["score"]), reason=l.get("reason", ""))
                      for l in row.get("lines", ()) or ())
        return Match(
            campaign_id=row.get("campaign_id", ""),
            creator_id=row.get("creator_id", ""),
            score=float(row.get("score", 0.0)),
            tier=row.get("tier", "C"),
            lines=lines,
            risks=tuple(row.get("risks", ()) or ()),
            evidence=tuple(row.get("evidence", ()) or ()),
            suggested_offer_usd=int(row.get("suggested_offer_usd", 0) or 0),
            projected_views_low=int(row.get("projected_views_low", 0) or 0),
            projected_views_high=int(row.get("projected_views_high", 0) or 0),
            excluded=bool(row.get("excluded", False)),
            exclusion_reason=row.get("exclusion_reason", ""),
        )

    # --------------------------------------------------------------- drafts
    def drafts(self, status: str = "") -> list:
        rows = self.store.read("drafts")
        if status:
            rows = [r for r in rows if r.get("status") == status]
        rows.sort(key=lambda r: r.get("created_at", ""))
        return rows

    def signature(self) -> str:
        name = self.settings.from_name or "Plugboard"
        address = self.settings.from_address
        return f"{name}\n{address}" if address else name

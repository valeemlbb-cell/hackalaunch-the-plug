"""The creator index: load, validate, and keep contact details out of the repo.

A creator record in `data/creators.seed.json` carries public audience numbers and an
opaque `contact_ref`. The address behind that ref lives in a local contacts file that is
gitignored and never committed, so the index can be shared, diffed and reviewed without
leaking anybody's inbox. `resolve_contact` is the only door between the two.
"""
from __future__ import annotations

import json
import os

from .models import Creator, Evidence, PlatformStats

REQUIRED_FIELDS = ("creator_id", "display_label")
CONTACTS_FILENAME = "contacts.local.json"


class CatalogError(ValueError):
    pass


def _platform(row: dict) -> PlatformStats:
    return PlatformStats(
        platform=str(row.get("platform", "")).lower(),
        followers=int(row.get("followers", 0) or 0),
        median_views=int(row.get("median_views", 0) or 0),
        engagement_rate=float(row.get("engagement_rate", 0.0) or 0.0),
        posts_last_30d=int(row.get("posts_last_30d", 0) or 0),
    )


def _evidence(row: dict) -> Evidence:
    return Evidence(
        fact=str(row.get("fact", "")).strip(),
        source_url=str(row.get("source_url", "")).strip(),
        observed_at=str(row.get("observed_at", "")).strip(),
    )


def creator_from_dict(row: dict) -> Creator:
    for field in REQUIRED_FIELDS:
        if not row.get(field):
            raise CatalogError(f"creator record is missing {field!r}: {row!r}")
    return Creator(
        creator_id=str(row["creator_id"]),
        display_label=str(row["display_label"]),
        name=str(row.get("name", "") or ""),
        languages=tuple(row.get("languages", ()) or ()),
        geo=str(row.get("geo", "") or ""),
        topics=tuple(row.get("topics", ()) or ()),
        audience_age_band=str(row.get("audience_age_band", "mixed") or "mixed"),
        platforms=tuple(_platform(p) for p in row.get("platforms", ()) or ()),
        cadence_per_week=float(row.get("cadence_per_week", 0.0) or 0.0),
        days_since_last_post=int(row.get("days_since_last_post", 999) or 999),
        price_usd_min=int(row.get("price_usd_min", 0) or 0),
        price_usd_max=int(row.get("price_usd_max", 0) or 0),
        accepts_paid_promo=bool(row.get("accepts_paid_promo", True)),
        discloses_ads=bool(row.get("discloses_ads", True)),
        contact_channel=str(row.get("contact_channel", "") or ""),
        contact_ref=str(row.get("contact_ref", "") or ""),
        safety_flags=tuple(row.get("safety_flags", ()) or ()),
        evidence=tuple(_evidence(e) for e in row.get("evidence", ()) or ()),
    )


def load_creators(path: str) -> list:
    if not os.path.isfile(path):
        raise CatalogError(f"creator index not found: {path}")
    with open(path, "r", encoding="utf-8-sig") as fh:
        try:
            rows = json.load(fh)
        except json.JSONDecodeError as exc:
            raise CatalogError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(rows, list):
        raise CatalogError(f"{path} must contain a JSON array of creator records")
    creators = [creator_from_dict(r) for r in rows]
    seen = set()
    for creator in creators:
        if creator.creator_id in seen:
            raise CatalogError(f"duplicate creator_id {creator.creator_id!r} in {path}")
        seen.add(creator.creator_id)
    return creators


def resolve_contact(creator: Creator, contacts_path: str) -> str:
    """contact_ref -> a real address, from an untracked local file. '' when unknown.

    A missing file is normal and not an error: the whole pipeline runs in dry-run without
    a single real address, which is exactly how the demo and the tests run.
    """
    if not creator.contact_ref or not os.path.isfile(contacts_path):
        return ""
    try:
        with open(contacts_path, "r", encoding="utf-8-sig") as fh:
            table = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return ""
    value = table.get(creator.contact_ref, "") if isinstance(table, dict) else ""
    return str(value or "")

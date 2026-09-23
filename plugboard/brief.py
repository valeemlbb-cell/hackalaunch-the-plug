"""Stage 1 - a founder's paragraph becomes a structured, matchable Campaign.

The parser is deterministic and runs with no network and no API key. An LLM, when one is
configured, is allowed to *fill gaps only*: it may propose values for fields the rules
left empty, and every proposal is validated against the same enum/range checks before it
is accepted. It can never overwrite a value the founder actually wrote down, which keeps
a hallucinated budget out of a real campaign.

Anything still missing lands in `campaign.warnings`, which the CLI and the dashboard show
in red - an unparsed budget must be visible, not silently defaulted to zero.
"""
from __future__ import annotations

import re
from dataclasses import replace

from . import taxonomy
from .models import Campaign
from .store import utc_now

MONEY_RE = re.compile(
    r"(?:(?P<cur>usd|us\$|\$|idr|rp)\s*)?(?P<num>\d[\d.,]*)\s*(?P<mult>k|rb|ribu|m|jt|juta)?",
    re.IGNORECASE,
)
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
PER_CREATOR_HINTS = ("per creator", "each creator", "per influencer", "per person", "/creator")
TOTAL_HINTS = ("total budget", "budget of", "we have", "budget is", "spend")
IDR_PER_USD = 16000  # display-only conversion; deals are stored in the currency agreed

DELIVERABLE_PATTERNS = (
    (r"(\d+)\s*(?:x\s*)?(?:short|reel|tiktok|vertical video|klip|clip)", "{n} x short-form video"),
    (r"(\d+)\s*(?:x\s*)?(?:dedicated\s*)?(?:youtube video|long form|long-form)", "{n} x long-form video"),
    (r"(\d+)\s*(?:x\s*)?(?:story|stories)", "{n} x story"),
    (r"(\d+)\s*(?:x\s*)?(?:post|tweet|thread)", "{n} x post/thread"),
    (r"(\d+)\s*(?:x\s*)?(?:podcast read|host read|ad read|mid-roll)", "{n} x host-read ad"),
    (r"(\d+)\s*(?:x\s*)?newsletter", "{n} x newsletter mention"),
)

AGE_RE = re.compile(r"(\d{2})\s*[-–to]{1,3}\s*(\d{2})")
EXCLUSION_WORDS = {
    "gambling_content": ("no gambling", "anti gambling", "not gambling", "judi"),
    "adult_content": ("no adult", "sfw only", "family safe", "brand safe"),
    "political_content": ("no politics", "apolitical", "non-political"),
    "alcohol_content": ("no alcohol", "alcohol free"),
}


def _money(text: str) -> int:
    """'$5k' / 'USD 5,000' / 'Rp8jt' -> integer USD. Returns 0 when nothing parses."""
    match = MONEY_RE.search(text or "")
    if not match:
        return 0
    raw = match.group("num").replace(",", "")
    if raw.count(".") == 1 and len(raw.split(".")[1]) == 3:
        raw = raw.replace(".", "")       # Indonesian thousands separator
    try:
        value = float(raw.replace(".", "") if raw.count(".") > 1 else raw)
    except ValueError:
        return 0
    mult = (match.group("mult") or "").lower()
    value *= {"k": 1_000, "rb": 1_000, "ribu": 1_000, "m": 1_000_000,
              "jt": 1_000_000, "juta": 1_000_000}.get(mult, 1)
    currency = (match.group("cur") or "").lower()
    if currency in ("idr", "rp"):
        value /= IDR_PER_USD
    return int(round(value))


def _sentences(text: str) -> list:
    return [s.strip() for s in re.split(r"[.\n;!?]+", text or "") if s.strip()]


def _budgets(text: str) -> tuple:
    total, per_creator = 0, 0
    for sentence in _sentences(text):
        low = sentence.lower()
        if any(h in low for h in PER_CREATOR_HINTS):
            per_creator = per_creator or _money(sentence)
        elif any(h in low for h in TOTAL_HINTS) or "budget" in low:
            total = total or _money(sentence)
    return total, per_creator


def _deliverables(text: str) -> tuple:
    low = (text or "").lower()
    out = []
    for pattern, label in DELIVERABLE_PATTERNS:
        for found in re.finditer(pattern, low):
            item = label.format(n=found.group(1))
            if item not in out:
                out.append(item)
    return tuple(out)


GOAL_SENTENCE_HINTS = ("goal", "objective", "we want", "we need", "target is",
                       "success looks like", "kpi", "optimi")


def _goal(text: str) -> str:
    """A sentence that announces the goal outranks a word used in passing.

    'we would rather not buy one big name' should not turn a waitlist campaign into a
    sales campaign, so goal words are counted inside goal-declaring sentences first and
    only fall back to the whole brief when none of them says so.
    """
    declared = " ".join(s for s in _sentences(text)
                        if any(h in s.lower() for h in GOAL_SENTENCE_HINTS))
    for scope in (declared, text):
        counts = taxonomy.count_from_map(scope, taxonomy.GOAL_WORDS)
        if counts:
            best = max(counts.values())
            for goal in ("signups", "app_installs", "sales", "community", "awareness"):
                if counts.get(goal) == best:
                    return goal
    return "awareness"


def _age_band(text: str) -> str:
    match = AGE_RE.search(text or "")
    if not match:
        return "mixed"
    low, high = int(match.group(1)), int(match.group(2))
    return f"{low}-{high}" if 10 <= low < high <= 80 else "mixed"


def _exclusions(text: str) -> tuple:
    low = f" {(text or '').lower()} "
    return tuple(flag for flag, words in EXCLUSION_WORDS.items() if any(w in low for w in words))


PRODUCT_RE = re.compile(
    r"(?:launching|we are building|we built|we made|introducing|our product is|product:)\s+"
    r"([A-Z][A-Za-z0-9][\w.\-]*(?:\s+[A-Z][\w.\-]*){0,2})")


def _product_name(text: str, fallback: str) -> str:
    """'We are launching Kilat, a savings app...' -> 'Kilat'. Falls back to the campaign id."""
    match = PRODUCT_RE.search(text or "")
    if match:
        return match.group(1).strip(" ,.;:")[:60]
    first = _sentences(text)
    return (first[0][:60] if first else fallback)


def _tagline(text: str, product: str) -> str:
    """The first sentence with the 'we are launching <Product>,' scaffolding removed."""
    sentences = _sentences(text)
    if not sentences:
        return ""
    line = sentences[0]
    match = PRODUCT_RE.search(line)
    if match:
        line = line[match.end():]
    line = line.strip(" ,.;:-")
    if line.lower().startswith(product.lower()):
        line = line[len(product):].strip(" ,.;:-")
    return line[:200]


def _kpis(text: str) -> tuple:
    low = (text or "").lower()
    out = []
    for word, kpi in (("cpm", "CPM"), ("cpa", "CPA"), ("roas", "ROAS"), ("view", "views"),
                      ("signup", "signups"), ("install", "installs"), ("click", "clicks"),
                      ("conversion", "conversions"), ("member", "members")):
        if word in low and kpi not in out:
            out.append(kpi)
    return tuple(out or ("views",))


def parse_brief(raw: str, campaign_id: str, llm=None) -> Campaign:
    """Free text -> Campaign. `llm` is optional and may only fill blanks."""
    text = (raw or "").strip()
    if not text:
        raise ValueError("brief is empty: pass a paragraph describing the product, audience and budget")

    total, per_creator = _budgets(text)
    languages = tuple(taxonomy.detect_from_map(text, taxonomy.LANGUAGE_WORDS))
    geos = taxonomy.detect_from_map(text, taxonomy.GEO_WORDS)
    platforms = tuple(taxonomy.detect_from_map(text, taxonomy.PLATFORM_WORDS))
    interests = tuple(taxonomy.detect_topics(text))
    dates = DATE_RE.findall(text)
    first_line = _sentences(text)[0] if _sentences(text) else text[:120]

    product = _product_name(text, campaign_id)
    campaign = Campaign(
        campaign_id=campaign_id,
        product=product,
        one_liner=_tagline(text, product),
        goal=_goal(text),
        languages=languages,
        geo=(geos[0] if geos else ""),
        audience_age_band=_age_band(text),
        interests=interests,
        platforms=platforms,
        budget_total_usd=total,
        budget_per_creator_usd=per_creator,
        deliverables=_deliverables(text),
        starts_on=(dates[0] if dates else ""),
        ends_on=(dates[1] if len(dates) > 1 else ""),
        kpis=_kpis(text),
        tone="direct",
        exclusions=_exclusions(text),
        is_paid_promotion=("gift" not in text.lower() and "unpaid" not in text.lower()),
        raw_brief=text,
        created_at=utc_now(),
    )
    campaign = _derive(campaign)
    if llm is not None:
        campaign = _fill_gaps_with_llm(campaign, llm)
        campaign = _derive(campaign)
    return replace(campaign, warnings=_warnings(campaign))


def _derive(campaign: Campaign) -> Campaign:
    """Fill the fields that follow arithmetically from what was parsed."""
    per_creator = campaign.budget_per_creator_usd
    if not per_creator and campaign.budget_total_usd:
        # No per-creator number given: assume a 6-creator portfolio, the mid-point of the
        # 4-8 spread that keeps a test campaign statistically readable.
        per_creator = int(campaign.budget_total_usd / 6)
    target_cpm = campaign.target_cpm_usd
    if not target_cpm:
        target_cpm = {"awareness": 6.0, "community": 9.0, "signups": 12.0,
                      "app_installs": 14.0, "sales": 18.0}.get(campaign.goal, 8.0)
    return replace(campaign, budget_per_creator_usd=per_creator, target_cpm_usd=target_cpm)


def _warnings(campaign: Campaign) -> tuple:
    out = []
    if not campaign.budget_total_usd:
        out.append("budget_total_usd not found in the brief - matching will rank on fit only")
    if not campaign.interests:
        out.append("no recognised topic in the brief - add a sentence about who it is for")
    if not campaign.platforms:
        out.append("no platform named - all platforms will be considered")
    if not campaign.languages:
        out.append("no language named - creators of any language may be matched")
    if not campaign.deliverables:
        out.append("no deliverable count found (e.g. '2 x TikTok') - offers will be generic")
    return tuple(out)


ENUM_FIELDS = {
    "goal": set(taxonomy.GOAL_WORDS),
    "geo": set(taxonomy.GEO_WORDS) | {""},
}
LIST_FIELDS = {
    "interests": set(taxonomy.TOPICS),
    "platforms": set(taxonomy.PLATFORM_WORDS),
    "languages": set(taxonomy.LANGUAGE_WORDS),
}


def _fill_gaps_with_llm(campaign: Campaign, llm) -> Campaign:
    """Ask the model for the blanks, then refuse anything outside the known vocabulary."""
    blanks = [f for f in ("goal", "geo", "interests", "platforms", "languages")
              if not getattr(campaign, f)]
    if not blanks:
        return campaign
    proposal = llm.suggest_campaign_fields(campaign.raw_brief, blanks)
    if not isinstance(proposal, dict):
        return campaign
    updates = {}
    for field, value in proposal.items():
        if field not in blanks:
            continue                      # never overwrite what the founder wrote
        if field in ENUM_FIELDS:
            if isinstance(value, str) and value in ENUM_FIELDS[field]:
                updates[field] = value
        elif field in LIST_FIELDS and isinstance(value, (list, tuple)):
            allowed = tuple(v for v in value if v in LIST_FIELDS[field])
            if allowed:
                updates[field] = allowed
    return replace(campaign, **updates) if updates else campaign

"""Stage 2 - score every creator against a campaign and say why, in words a founder can argue with.

Shape of the answer, in order:

  1. HARD FILTERS      a creator is excluded outright, with a reason string, when the deal
                       is impossible (wrong language, refuses paid work, on the blocklist,
                       carries a flag the founder excluded, or fails the authenticity check).
  2. SEVEN SUB-SCORES  each 0..1, each carrying its own sentence. The weighted sum is the score.
  3. PORTFOLIO PICK    the top list is then diversified so a founder does not spend the whole
                       budget inside one topic cluster.

Every number below is a constant with a name and a comment. Nothing is learned, nothing is
random: run it twice on the same inputs and you get the same ranking, which is the point -
a founder can be shown exactly which fact moved a creator up or down.
"""
from __future__ import annotations

from . import taxonomy
from .models import Campaign, Creator, Match, ScoreLine

WEIGHTS = {
    "topic_fit":         0.26,   # does this audience care about the category at all
    "audience_fit":      0.18,   # language, geography, age band
    "reach_fit":         0.14,   # is the size right for THIS goal, not just big
    "engagement_quality": 0.12,  # do the viewers actually do anything
    "freshness":         0.10,   # posting now, not a dormant account
    "budget_fit":        0.12,   # can the founder afford it, at what CPM
    "platform_fit":      0.08,   # active where the campaign wants to run
}

# Views-per-follower outside this band is the authenticity tripwire. Below the floor the
# audience does not watch (bought followers); above the ceiling the follower count is not
# where the views come from, which is fine for TikTok but must be flagged, not scored.
VIEW_RATIO_FLOOR = 0.008
VIEW_RATIO_CEILING = 3.0

# Goal -> the median-view band that historically performs for that goal. Awareness wants
# raw reach; sales convert better with smaller, closer audiences.
GOAL_REACH_BAND = {
    "awareness":    (20_000, 2_000_000),
    "community":    (5_000, 300_000),
    "signups":      (4_000, 200_000),
    "app_installs": (8_000, 500_000),
    "sales":        (3_000, 150_000),
}
GOAL_ENGAGEMENT_TARGET = {
    "awareness": 0.02, "community": 0.05, "signups": 0.045,
    "app_installs": 0.035, "sales": 0.055,
}
FRESH_FULL_DAYS = 7          # posted within a week = full marks
FRESH_ZERO_DAYS = 60         # nothing for two months = zero
CADENCE_TARGET = 3.0         # posts/week at which cadence stops adding value
TIER_A, TIER_B = 0.68, 0.50  # score thresholds
DIVERSITY_MAX_PER_TOPIC = 2  # at most this many picks share a primary topic


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


# --------------------------------------------------------------------- filters
def hard_filter(campaign: Campaign, creator: Creator, blocked: set) -> str:
    """Return a reason string when the creator cannot be used at all, else ''."""
    if creator.creator_id in blocked:
        return "on the blocklist (opted out or previously declined) - never contacted again"
    if campaign.is_paid_promotion and not creator.accepts_paid_promo:
        return "does not accept paid promotion"
    if campaign.is_paid_promotion and not creator.discloses_ads:
        return "does not disclose paid posts - refused on advertising-disclosure grounds"
    clash = sorted(set(campaign.exclusions) & set(creator.safety_flags))
    if clash:
        return f"carries a flag the brief excludes: {', '.join(clash)}"
    if campaign.languages and creator.languages:
        if not set(campaign.languages) & set(creator.languages):
            return (f"no shared language (campaign {'/'.join(campaign.languages)}, "
                    f"creator {'/'.join(creator.languages)})")
    top = creator.best_platform()
    if top and top.followers > 1000:
        ratio = top.median_views / max(top.followers, 1)
        if ratio < VIEW_RATIO_FLOOR:
            return (f"authenticity check failed: {top.median_views:,} median views against "
                    f"{top.followers:,} followers ({ratio:.3f} views/follower) - inflated audience")
    return ""


# ---------------------------------------------------------------- sub-scores
def score_topic(campaign: Campaign, creator: Creator) -> ScoreLine:
    if not campaign.interests or not creator.topics:
        return ScoreLine("topic_fit", WEIGHTS["topic_fit"], 0.35,
                         "no topic on one side - scored neutral, verify by hand")
    best = {}
    for want in campaign.interests:
        for have in creator.topics:
            affinity = taxonomy.topic_affinity(want, have)
            if affinity > best.get(want, 0.0):
                best[want] = affinity
    # Weighted towards the first-listed campaign interests: the founder's headline topic
    # counts more than the fifth thing they mentioned in passing.
    total_weight = sum(1.0 / (i + 1) for i in range(len(campaign.interests)))
    earned = sum(best.get(t, 0.0) / (i + 1) for i, t in enumerate(campaign.interests))
    score = _clamp(earned / total_weight) if total_weight else 0.0
    exact = sorted(t for t in campaign.interests if best.get(t) == 1.0)
    near = sorted(t for t in campaign.interests if best.get(t) == 0.5)
    parts = []
    if exact:
        parts.append(f"exact topic overlap on {', '.join(exact)}")
    if near:
        parts.append(f"adjacent audience for {', '.join(near)}")
    if not parts:
        parts.append(f"creator covers {', '.join(creator.topics[:3])}, none of the campaign topics")
    return ScoreLine("topic_fit", WEIGHTS["topic_fit"], round(score, 3), "; ".join(parts))


def score_audience(campaign: Campaign, creator: Creator) -> ScoreLine:
    parts, score = [], 0.0
    if campaign.languages and creator.languages:
        shared = sorted(set(campaign.languages) & set(creator.languages))
        score += 0.45
        parts.append(f"speaks {'/'.join(shared)}")
    elif not campaign.languages:
        score += 0.30
        parts.append("campaign named no language")
    if campaign.geo and creator.geo:
        if campaign.geo == creator.geo or campaign.geo == "GLOBAL":
            score += 0.35
            parts.append(f"based in {creator.geo}, the campaign's market")
        else:
            parts.append(f"based in {creator.geo}, campaign targets {campaign.geo}")
    elif not campaign.geo:
        score += 0.20
        parts.append("no geography constraint")
    want, have = campaign.audience_age_band, creator.audience_age_band
    if want == "mixed" or have == "mixed" or want == have:
        score += 0.20
        parts.append(f"audience age {have or 'unknown'} fits")
    else:
        parts.append(f"audience age {have} vs requested {want}")
    return ScoreLine("audience_fit", WEIGHTS["audience_fit"], round(_clamp(score), 3), "; ".join(parts))


def score_reach(campaign: Campaign, creator: Creator) -> ScoreLine:
    top = creator.best_platform(campaign.platforms) or creator.best_platform()
    if not top or top.median_views <= 0:
        return ScoreLine("reach_fit", WEIGHTS["reach_fit"], 0.2, "no view data on record")
    low, high = GOAL_REACH_BAND.get(campaign.goal, (5_000, 500_000))
    views = top.median_views
    if low <= views <= high:
        score, note = 1.0, f"{views:,} median views on {top.platform} sits inside the {campaign.goal} band"
    elif views < low:
        score = _clamp(views / low)
        note = f"{views:,} median views is below the {low:,} floor for {campaign.goal}"
    else:
        # Too big is a soft penalty, not a wall: reach still has value, it just costs more.
        score = _clamp(1.0 - min((views - high) / (high * 4.0), 0.6))
        note = f"{views:,} median views is above the {high:,} ceiling for {campaign.goal} - expect a premium"
    return ScoreLine("reach_fit", WEIGHTS["reach_fit"], round(score, 3), note)


def score_engagement(campaign: Campaign, creator: Creator) -> ScoreLine:
    top = creator.best_platform(campaign.platforms) or creator.best_platform()
    if not top or top.engagement_rate <= 0:
        return ScoreLine("engagement_quality", WEIGHTS["engagement_quality"], 0.2,
                         "no engagement data on record")
    target = GOAL_ENGAGEMENT_TARGET.get(campaign.goal, 0.03)
    score = _clamp(top.engagement_rate / (target * 1.5))
    note = (f"{top.engagement_rate * 100:.1f}% engagement on {top.platform} "
            f"against a {target * 100:.1f}% target for {campaign.goal}")
    return ScoreLine("engagement_quality", WEIGHTS["engagement_quality"], round(score, 3), note)


def score_freshness(campaign: Campaign, creator: Creator) -> ScoreLine:
    days = creator.days_since_last_post
    if days <= FRESH_FULL_DAYS:
        recency = 1.0
    elif days >= FRESH_ZERO_DAYS:
        recency = 0.0
    else:
        recency = 1.0 - (days - FRESH_FULL_DAYS) / (FRESH_ZERO_DAYS - FRESH_FULL_DAYS)
    cadence = _clamp(creator.cadence_per_week / CADENCE_TARGET)
    score = _clamp(0.7 * recency + 0.3 * cadence)
    note = f"last posted {days}d ago, about {creator.cadence_per_week:g} posts/week"
    return ScoreLine("freshness", WEIGHTS["freshness"], round(score, 3), note)


def score_budget(campaign: Campaign, creator: Creator) -> ScoreLine:
    budget = campaign.budget_per_creator_usd
    ask_low, ask_high = creator.price_usd_min, creator.price_usd_max
    if not budget:
        return ScoreLine("budget_fit", WEIGHTS["budget_fit"], 0.4,
                         "campaign gave no budget - price fit unknown")
    if not ask_high:
        return ScoreLine("budget_fit", WEIGHTS["budget_fit"], 0.4,
                         f"no published rate; campaign can spend ${budget:,}/creator")
    if budget < ask_low:
        score = _clamp(budget / max(ask_low, 1))
        note = f"asks ${ask_low:,}-${ask_high:,}, campaign has ${budget:,}/creator - short by ${ask_low - budget:,}"
    else:
        score = 1.0
        note = f"asks ${ask_low:,}-${ask_high:,}, inside the ${budget:,}/creator budget"
    top = creator.best_platform(campaign.platforms) or creator.best_platform()
    if top and top.median_views > 0 and campaign.target_cpm_usd:
        cpm = (ask_high or ask_low) / (top.median_views / 1000.0)
        note += f"; implied CPM ${cpm:.2f} vs target ${campaign.target_cpm_usd:.2f}"
        if cpm > campaign.target_cpm_usd:
            score = _clamp(score * (campaign.target_cpm_usd / cpm))
    return ScoreLine("budget_fit", WEIGHTS["budget_fit"], round(score, 3), note)


def score_platform(campaign: Campaign, creator: Creator) -> ScoreLine:
    have = {p.platform for p in creator.platforms}
    if not campaign.platforms:
        return ScoreLine("platform_fit", WEIGHTS["platform_fit"], 0.6,
                         f"campaign named no platform; creator is on {', '.join(sorted(have)) or 'nothing'}")
    shared = sorted(set(campaign.platforms) & have)
    score = _clamp(len(shared) / len(campaign.platforms))
    note = (f"active on {', '.join(shared)}" if shared
            else f"not on {', '.join(campaign.platforms)} (has {', '.join(sorted(have)) or 'nothing'})")
    return ScoreLine("platform_fit", WEIGHTS["platform_fit"], round(score, 3), note)


SCORERS = (score_topic, score_audience, score_reach, score_engagement,
           score_freshness, score_budget, score_platform)


# ------------------------------------------------------------------- assembly
def risks_for(campaign: Campaign, creator: Creator) -> tuple:
    out = []
    top = creator.best_platform(campaign.platforms) or creator.best_platform()
    if top and top.followers > 1000:
        ratio = top.median_views / max(top.followers, 1)
        if ratio > VIEW_RATIO_CEILING:
            out.append(f"views ({top.median_views:,}) far exceed followers ({top.followers:,}) - "
                       "check the last 5 posts before paying")
    if creator.days_since_last_post > 21:
        out.append(f"quiet for {creator.days_since_last_post} days - confirm they are still active")
    if campaign.budget_per_creator_usd and creator.price_usd_min > campaign.budget_per_creator_usd:
        out.append("asking price is above the per-creator budget - expect to negotiate or cut scope")
    if creator.safety_flags:
        out.append("content flags on record: " + ", ".join(creator.safety_flags))
    if not creator.contact_channel:
        out.append("no contact channel on record - cannot be reached yet")
    return tuple(out)


def projected_views(campaign: Campaign, creator: Creator) -> tuple:
    """A deliberately wide band. Never presented as a guarantee - see docs/SAFETY.md."""
    top = creator.best_platform(campaign.platforms) or creator.best_platform()
    if not top or top.median_views <= 0:
        return (0, 0)
    per_post = top.median_views
    posts = max(1, len(campaign.deliverables) or 1)
    return (int(per_post * 0.5 * posts), int(per_post * 1.6 * posts))


def suggested_offer(campaign: Campaign, creator: Creator) -> int:
    """Open at the creator's own floor, capped by the per-creator budget."""
    budget = campaign.budget_per_creator_usd
    ask = creator.price_usd_min or creator.price_usd_max
    if not ask:
        return budget
    if not budget:
        return ask
    return int(min(max(ask, int(budget * 0.7)), budget))


def tier_for(score: float) -> str:
    if score >= TIER_A:
        return "A"
    return "B" if score >= TIER_B else "C"


def match_one(campaign: Campaign, creator: Creator, blocked: set = frozenset()) -> Match:
    reason = hard_filter(campaign, creator, set(blocked))
    if reason:
        return Match(campaign_id=campaign.campaign_id, creator_id=creator.creator_id,
                     score=0.0, tier="C", excluded=True, exclusion_reason=reason)
    lines = tuple(scorer(campaign, creator) for scorer in SCORERS)
    score = round(sum(line.contribution for line in lines), 4)
    low, high = projected_views(campaign, creator)
    return Match(
        campaign_id=campaign.campaign_id,
        creator_id=creator.creator_id,
        score=score,
        tier=tier_for(score),
        lines=lines,
        risks=risks_for(campaign, creator),
        evidence=tuple(e.line() for e in creator.evidence[:3]),
        suggested_offer_usd=suggested_offer(campaign, creator),
        projected_views_low=low,
        projected_views_high=high,
    )


def rank(campaign: Campaign, creators: list, blocked: set = frozenset()) -> list:
    matches = [match_one(campaign, c, blocked) for c in creators]
    matches.sort(key=lambda m: (m.excluded, -m.score, m.creator_id))
    return matches


def diversify(matches: list, creators: list, limit: int,
              max_per_topic: int = DIVERSITY_MAX_PER_TOPIC) -> list:
    """Pick `limit` matches while keeping the portfolio spread across topics.

    A skipped-over creator is not discarded; it simply falls below the ones that widen the
    coverage. If the cap leaves us short, the highest remaining scores fill the gap, so the
    function always returns min(limit, len(eligible)) picks.
    """
    by_id = {c.creator_id: c for c in creators}
    eligible = [m for m in matches if not m.excluded]
    picked, used, deferred = [], {}, []
    for match in eligible:
        if len(picked) >= limit:
            break
        creator = by_id.get(match.creator_id)
        primary = (creator.topics[0] if creator and creator.topics else "unknown")
        if used.get(primary, 0) >= max_per_topic:
            deferred.append(match)
            continue
        used[primary] = used.get(primary, 0) + 1
        picked.append(match)
    for match in deferred:
        if len(picked) >= limit:
            break
        picked.append(match)
    return picked

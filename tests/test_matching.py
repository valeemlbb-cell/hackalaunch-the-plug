"""Stage 2: the ranking, the filters, and the promise that every score can be explained."""
from __future__ import annotations

from dataclasses import replace

from plugboard import matching
from plugboard.matching import WEIGHTS, diversify, hard_filter, match_one, rank


def by_id(creators, creator_id):
    return next(c for c in creators if c.creator_id == creator_id)


def test_weights_sum_to_one():
    assert round(sum(WEIGHTS.values()), 6) == 1.0


def test_top_match_is_the_on_topic_indonesian_micro_creator(campaign, creators):
    ranked = [m for m in rank(campaign, creators) if not m.excluded]
    assert ranked[0].creator_id in ("c014", "c002")
    assert ranked[0].tier == "A"


def test_every_scored_match_carries_a_reason_for_each_dimension(campaign, creators):
    match = match_one(campaign, by_id(creators, "c014"))
    assert {l.name for l in match.lines} == set(WEIGHTS)
    assert all(l.reason.strip() for l in match.lines)
    assert round(sum(l.contribution for l in match.lines), 4) == match.score


def test_score_is_deterministic(campaign, creators):
    first = [(m.creator_id, m.score) for m in rank(campaign, creators)]
    second = [(m.creator_id, m.score) for m in rank(campaign, creators)]
    assert first == second


# ------------------------------------------------------------------- filters
def test_language_mismatch_is_a_hard_filter(campaign, creators):
    assert "no shared language" in hard_filter(campaign, by_id(creators, "c012"), set())


def test_excluded_safety_flag_is_a_hard_filter(campaign, creators):
    assert "gambling_content" in hard_filter(campaign, by_id(creators, "c008"), set())


def test_creator_who_refuses_paid_promotion_is_filtered_out(campaign, creators):
    assert "paid promotion" in hard_filter(campaign, by_id(creators, "c011"), set())


def test_creator_who_never_labels_ads_is_refused(campaign, creators):
    assert "disclosure" in hard_filter(campaign, by_id(creators, "c017"), set())


def test_inflated_audience_fails_the_authenticity_check(campaign, creators):
    reason = hard_filter(campaign, by_id(creators, "c010"), set())
    assert "authenticity" in reason and "inflated" in reason


def test_blocklisted_creator_is_never_matched(campaign, creators):
    match = match_one(campaign, by_id(creators, "c014"), blocked={"c014"})
    assert match.excluded and "blocklist" in match.exclusion_reason


def test_excluded_matches_score_zero_and_sort_last(campaign, creators):
    ranked = rank(campaign, creators)
    assert all(m.score == 0.0 for m in ranked if m.excluded)
    first_excluded = next(i for i, m in enumerate(ranked) if m.excluded)
    assert all(m.excluded for m in ranked[first_excluded:])


# -------------------------------------------------------------------- scoring
def test_dormant_creator_loses_freshness_and_gains_a_risk(campaign, creators):
    match = match_one(campaign, by_id(creators, "c009"))
    freshness = next(l for l in match.lines if l.name == "freshness")
    assert freshness.score <= 0.05          # recency is zeroed; only a trace of cadence remains
    assert any("quiet for" in r for r in match.risks)


def test_price_above_budget_lowers_budget_fit_and_is_flagged(campaign, creators):
    match = match_one(campaign, by_id(creators, "c007"))
    budget = next(l for l in match.lines if l.name == "budget_fit")
    assert budget.score < 1.0
    assert any("above the per-creator budget" in r for r in match.risks)


def test_reach_far_above_the_goal_band_is_penalised_not_rewarded(campaign, creators):
    huge = replace(by_id(creators, "c002"), creator_id="huge",
                   platforms=(replace(by_id(creators, "c002").platforms[0], median_views=1_500_000),))
    right_sized = match_one(campaign, by_id(creators, "c002"))
    oversized = match_one(campaign, huge)
    assert oversized.score < right_sized.score


def test_suggested_offer_never_exceeds_the_per_creator_budget(campaign, creators):
    for match in rank(campaign, creators):
        if not match.excluded:
            assert match.suggested_offer_usd <= campaign.budget_per_creator_usd


def test_projection_is_a_band_not_a_promise(campaign, creators):
    match = match_one(campaign, by_id(creators, "c002"))
    assert match.projected_views_low < match.projected_views_high


# ------------------------------------------------------------------ portfolio
def test_diversify_caps_how_much_of_the_budget_sits_in_one_topic(campaign, creators):
    ranked = rank(campaign, creators)
    picks = diversify(ranked, creators, limit=5, max_per_topic=2)
    primaries = [by_id(creators, m.creator_id).topics[0] for m in picks]
    assert max(primaries.count(p) for p in set(primaries)) <= 2 + 1  # +1 for backfill
    assert len(picks) == 5


def test_diversify_returns_what_it_can_when_the_pool_is_small(campaign, creators):
    ranked = rank(campaign, creators)
    eligible = [m for m in ranked if not m.excluded]
    picks = diversify(ranked, creators, limit=len(eligible) + 10)
    assert len(picks) == len(eligible)


def test_missing_view_data_scores_low_but_does_not_crash(campaign, creators):
    blank = replace(by_id(creators, "c002"), platforms=())
    match = match_one(campaign, blank)
    assert not match.excluded
    assert next(l for l in match.lines if l.name == "reach_fit").score < 0.5

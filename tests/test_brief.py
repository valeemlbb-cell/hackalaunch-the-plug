"""Stage 1: does a paragraph of prose become the campaign a founder actually described?"""
from __future__ import annotations

import pytest

from plugboard.brief import _money, parse_brief


def test_parses_the_sample_brief_into_a_matchable_campaign(campaign):
    assert campaign.product == "Kilat"
    assert campaign.goal == "signups"
    assert campaign.languages == ("id",)
    assert campaign.geo == "ID"
    assert campaign.audience_age_band == "18-24"
    assert "personal_finance" in campaign.interests
    assert set(campaign.platforms) == {"tiktok", "youtube"}
    assert campaign.budget_total_usd == 3000
    assert campaign.budget_per_creator_usd == 350
    assert campaign.starts_on == "2026-10-01" and campaign.ends_on == "2026-10-21"
    assert "gambling_content" in campaign.exclusions


def test_goal_words_used_in_passing_do_not_hijack_the_declared_goal():
    text = ("We are launching Nadi. Goal for this campaign is signups on the waitlist. "
            "We would rather not buy one big name. Budget is $2,000.")
    assert parse_brief(text, "nadi").goal == "signups"


def test_short_topic_words_do_not_match_inside_other_words():
    """'raid' must not become AI and 'care' must not become automotive."""
    text = ("We are building Tenang, a meditation app. We care about calm. Nobody should "
            "raid their savings. Budget is $1,000.")
    interests = parse_brief(text, "tenang").interests
    assert "ai" not in interests
    assert "automotive" not in interests


def test_two_by_tiktok_is_not_a_request_for_twitter():
    text = "We are launching Kopi. We want 2 x TikTok posts. Budget is $500."
    assert "x" not in parse_brief(text, "kopi").platforms


def test_missing_budget_is_surfaced_as_a_warning_not_a_silent_zero():
    campaign = parse_brief("We are launching Sapa, a crypto wallet for students.", "sapa")
    assert campaign.budget_total_usd == 0
    assert any("budget" in w for w in campaign.warnings)


def test_empty_brief_is_refused():
    with pytest.raises(ValueError):
        parse_brief("   ", "nope")


@pytest.mark.parametrize("text,expected", [
    ("budget is $5k", 5000),
    ("budget is USD 12,500", 12500),
    ("budget of $750", 750),
    ("budget Rp8jt", 500),          # 8,000,000 IDR at the documented 16,000 display rate
    ("no numbers here", 0),
])
def test_money_parsing(text, expected):
    assert _money(text) == expected


def test_deliverable_counts_are_extracted():
    campaign = parse_brief(
        "We are launching Jaga. We want 3 x TikTok shorts and 1 x YouTube video. Budget is $900.",
        "jaga")
    assert "3 x short-form video" in campaign.deliverables
    assert "1 x long-form video" in campaign.deliverables


def test_llm_may_fill_a_blank_but_never_overwrite_a_parsed_value():
    class Liar:
        def suggest_campaign_fields(self, raw, blanks):
            # proposes a value for a blank field (allowed) and for a filled one (ignored)
            return {"geo": "US", "goal": "sales", "interests": ["crypto"]}

    text = "We are launching Ombak. Goal is signups. Budget is $1,000."
    campaign = parse_brief(text, "ombak", llm=Liar())
    assert campaign.goal == "signups"        # the founder said so; the model does not get a vote
    assert campaign.geo == "US"              # this one really was blank
    assert campaign.interests == ("crypto",)


def test_llm_values_outside_the_vocabulary_are_dropped():
    class Hallucinator:
        def suggest_campaign_fields(self, raw, blanks):
            return {"goal": "world_domination", "interests": ["underwater_basket_weaving"]}

    campaign = parse_brief("We are launching Riak. Budget is $400.", "riak", llm=Hallucinator())
    assert campaign.goal in ("awareness", "signups", "sales", "app_installs", "community")
    assert "underwater_basket_weaving" not in campaign.interests

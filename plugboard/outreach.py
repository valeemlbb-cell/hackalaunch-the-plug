"""Stage 3 - write the message. One creator, one reason, one ask.

Three things this module refuses to produce, because each one is a disqualifier in the
brief and a good way to get a domain burned:

  * a message with no specific, sourced reason for contacting THIS creator,
  * a paid-promotion pitch that does not say the post must be disclosed as an ad,
  * a message with no opt-out line.

`compose` raises rather than returning a draft that breaks any of those, so a broken
template fails at build time instead of arriving in somebody's inbox.

Drafts are text only. Nothing here sends; see approval.py and senders.py.
"""
from __future__ import annotations

from dataclasses import replace

from . import taxonomy
from .models import Campaign, Creator, Draft, Match, content_hash
from .store import utc_now

OPT_OUT_EN = "If this is not for you, reply 'no thanks' and I will not write again."
OPT_OUT_ID = "Kalau nggak cocok, bales 'nggak dulu' aja, aku nggak akan kirim lagi."
DISCLOSURE_EN = ("This is a paid collaboration, so the post has to be marked as an ad "
                 "(#ad / paid partnership label) on your side and ours.")
DISCLOSURE_ID = ("Ini kerja sama berbayar, jadi postingannya wajib ditandai iklan "
                 "(#ad / label paid partnership) di sisi kamu dan kami.")
MAX_BODY_CHARS = 1400          # longer than this and nobody reads it
MIN_BODY_CHARS = 220


class OutreachError(ValueError):
    """A draft could not be built safely. The message is user-facing."""


def _money(amount: int) -> str:
    return f"${amount:,}"


def _views(low: int, high: int, language: str) -> str:
    if not high:
        return ("belum ada data views di catatan kami" if language == "id"
                else "we do not have view data on record yet")
    if language == "id":
        return f"sekitar {low:,}-{high:,} views total, dihitung dari median kamu belakangan ini"
    return f"roughly {low:,}-{high:,} views across the deliverables, based on your recent medians"


def _deliverables(campaign: Campaign) -> str:
    if not campaign.deliverables:
        return "one piece of content, format your call"
    return ", ".join(campaign.deliverables)


def _salutation(creator: Creator, language: str) -> str:
    """The index is anonymised by default, so a draft opens neutrally rather than
    addressing someone by a label a scout invented. Fill `name` and it is used instead."""
    if creator.name:
        return creator.name
    return "kak" if language == "id" else "there"


def _hook(match: Match, creator: Creator) -> str:
    """The single sourced fact that justifies the email. No fact, no send."""
    if match.evidence:
        return match.evidence[0]
    if creator.evidence:
        return creator.evidence[0].line()
    return ""


def _why_lines(match: Match, campaign: Campaign, creator: Creator,
               language: str, count: int = 2) -> list:
    """The top scoring dimensions, restated in the creator's own language.

    The English `reason` strings on a ScoreLine are written for the founder's dashboard;
    pasting them into an Indonesian email would read like a machine. So the same facts are
    re-rendered here from the underlying numbers.
    """
    ranked = sorted(match.lines, key=lambda l: -l.contribution)[:count]
    return [_localise(line, campaign, creator, language) for line in ranked]


def _localise(line, campaign: Campaign, creator: Creator, language: str) -> str:
    top = creator.best_platform(campaign.platforms) or creator.best_platform()
    shared = [t for t in campaign.interests if t in creator.topics] or list(creator.topics[:2])
    topics = ", ".join(taxonomy.topic_label(t, language) for t in shared[:2])
    if line.name == "topic_fit":
        return (f"audiens kamu udah biasa sama konten {topics}" if language == "id"
                else f"your audience already follows {topics}")
    if line.name == "audience_fit":
        band = creator.audience_age_band
        return (f"audiensnya {band} di {creator.geo}, persis yang kami cari" if language == "id"
                else f"a {band} audience in {creator.geo}, which is the market we want")
    if line.name == "reach_fit" and top:
        return (f"{top.median_views:,} views rata-rata di {top.platform}" if language == "id"
                else f"{top.median_views:,} median views on {top.platform}")
    if line.name == "engagement_quality" and top:
        return (f"engagement {top.engagement_rate * 100:.1f}% di {top.platform}" if language == "id"
                else f"{top.engagement_rate * 100:.1f}% engagement on {top.platform}")
    if line.name == "freshness":
        return (f"posting sekitar {creator.cadence_per_week:g}x seminggu dan masih aktif"
                if language == "id"
                else f"posting about {creator.cadence_per_week:g} times a week and still active")
    if line.name == "budget_fit":
        return ("rate kamu masuk di budget kami" if language == "id"
                else "your rate sits inside our budget")
    if line.name == "platform_fit":
        platforms = ", ".join(sorted({p.platform for p in creator.platforms} & set(campaign.platforms)))
        return (f"kamu aktif di {platforms or 'platform yang kami tuju'}" if language == "id"
                else f"you are active on {platforms or 'the platforms we are running on'}")
    return line.reason


TEMPLATE_EN = """Hi {salutation},

{hook_sentence}

I am working with {product}{one_liner}. I am looking for {deliverables} and I think your audience fits: {why}.

Offer: {offer} for {deliverables}, {timeline}. Expected scale on our side is {views} - an estimate from your public numbers, not a target you have to hit.

{disclosure}

If you are interested, reply with your rate and the earliest slot you have and I will send a one-page brief. Happy to send the product over first so you can decide whether it is worth your audience's time.

{opt_out}

{signature}"""

TEMPLATE_ID = """Halo {salutation},

{hook_sentence}

Aku lagi bantu {product}{one_liner}. Yang dicari: {deliverables}, dan kayaknya audiens kamu cocok: {why}.

Penawaran: {offer} untuk {deliverables}, {timeline}. Perkiraan jangkauan {views} - itu estimasi dari angka publik kamu, bukan target yang wajib kekejar.

{disclosure}

Kalau tertarik, bales aja rate kamu sama slot paling cepet yang ada, nanti aku kirim brief 1 halaman. Produknya juga bisa aku kirim duluan biar kamu bisa nilai sendiri layak atau nggak buat audiens kamu.

{opt_out}

{signature}"""


def compose(campaign: Campaign, creator: Creator, match: Match, *,
            channel: str = "", signature: str = "Plugboard", draft_id: str = "",
            llm=None) -> Draft:
    """Build one first-touch draft. Raises OutreachError when it would be unsafe to send."""
    if match.excluded:
        raise OutreachError(f"{creator.creator_id} is excluded: {match.exclusion_reason}")
    hook = _hook(match, creator)
    if not hook:
        raise OutreachError(
            f"{creator.creator_id} has no sourced fact on record. Plugboard does not write "
            "'I love your content' emails - add evidence to the creator record first.")

    language = "id" if "id" in creator.languages else "en"
    template = TEMPLATE_ID if language == "id" else TEMPLATE_EN
    opt_out = OPT_OUT_ID if language == "id" else OPT_OUT_EN
    disclosure = (DISCLOSURE_ID if language == "id" else DISCLOSURE_EN) if campaign.is_paid_promotion else ""

    hook_sentence = (f"Yang bikin aku kontak kamu: {hook}." if language == "id"
                     else f"What caught my eye: {hook}.")
    if campaign.starts_on and campaign.ends_on:
        timeline = f"{campaign.starts_on} - {campaign.ends_on}"
    else:
        timeline = "waktunya fleksibel" if language == "id" else "timing is flexible"
    tagline = (campaign.one_liner or "").strip()
    one_liner = f" - {tagline}" if tagline and tagline.lower() != campaign.product.lower() else ""

    body = template.format(
        salutation=_salutation(creator, language),
        hook_sentence=hook_sentence,
        product=campaign.product,
        one_liner=one_liner,
        deliverables=_deliverables(campaign),
        why="; ".join(_why_lines(match, campaign, creator, language)),
        offer=_money(match.suggested_offer_usd) if match.suggested_offer_usd else "rate to be agreed",
        timeline=timeline,
        views=_views(match.projected_views_low, match.projected_views_high, language),
        disclosure=disclosure,
        opt_out=opt_out,
        signature=signature,
    )
    body = "\n".join(line.rstrip() for line in body.splitlines())
    while "\n\n\n" in body:
        body = body.replace("\n\n\n", "\n\n")

    if llm is not None:
        body = _polish(body, campaign, llm)

    who = creator.name or creator.display_label
    subject = (f"{campaign.product} x {who} - paid collaboration"
               if campaign.is_paid_promotion else f"{campaign.product} x {who} - collaboration")

    draft = Draft(
        draft_id=draft_id or f"d-{campaign.campaign_id}-{creator.creator_id}",
        campaign_id=campaign.campaign_id,
        creator_id=creator.creator_id,
        channel=channel or creator.contact_channel or "email",
        subject=subject[:120],
        body=body,
        language=language,
        created_at=utc_now(),
    )
    validate(draft, campaign)
    return replace(draft, body_hash=content_hash({"subject": draft.subject, "body": draft.body}))


def validate(draft: Draft, campaign: Campaign) -> None:
    """The gate every draft passes before it can even be queued."""
    body = draft.body or ""
    if len(body) < MIN_BODY_CHARS:
        raise OutreachError(f"draft {draft.draft_id} is too short to be a real message ({len(body)} chars)")
    if len(body) > MAX_BODY_CHARS:
        raise OutreachError(f"draft {draft.draft_id} is {len(body)} chars, over the {MAX_BODY_CHARS} limit")
    opt_outs = (OPT_OUT_EN[:24], OPT_OUT_ID[:24], "not write again", "nggak akan kirim lagi")
    if not any(o in body for o in opt_outs):
        raise OutreachError(f"draft {draft.draft_id} has no opt-out line")
    if campaign.is_paid_promotion and not any(tag in body.lower() for tag in ("#ad", "paid partnership")):
        raise OutreachError(f"draft {draft.draft_id} is a paid pitch with no advertising-disclosure line")
    for placeholder in ("{", "}"):
        if placeholder in body:
            raise OutreachError(f"draft {draft.draft_id} still contains an unfilled placeholder")


def _polish(body: str, campaign: Campaign, llm) -> str:
    """Optional rewrite for tone. Rejected unless it keeps every safety line intact."""
    try:
        candidate = llm.rewrite_outreach(body, campaign.tone)
    except Exception:
        return body
    if not isinstance(candidate, str) or not candidate.strip():
        return body
    keep = [OPT_OUT_EN[:24], OPT_OUT_ID[:24]]
    if not any(k in candidate for k in keep):
        return body
    if campaign.is_paid_promotion and not any(t in candidate.lower() for t in ("#ad", "paid partnership")):
        return body
    if len(candidate) > MAX_BODY_CHARS:
        return body
    return candidate


# ------------------------------------------------------------------- replies
INTENT_RULES = (
    ("unsubscribe", ("unsubscribe", "stop emailing", "remove me", "do not contact", "jangan kirim lagi",
                     "no thanks", "nggak dulu", "gak minat", "not interested")),
    ("rate_question", ("how much", "what is the rate", "budget?", "berapa", "rate card", "my rate is",
                       "price", "harga")),
    ("interested", ("interested", "sounds good", "let's do", "lets do", "send the brief", "i am in",
                    "im in", "mau", "boleh", "tertarik", "deal")),
    ("later", ("next month", "later", "busy right now", "after", "q4", "nanti", "lagi sibuk")),
    ("question", ("?",)),
)
INTENT_ACTION = {
    "unsubscribe": "blocklist the creator permanently and close the thread - no reply is sent",
    "rate_question": "answer with the offer and the deliverable list, then draft a deal",
    "interested": "create a deal in negotiating state and draft the one-page brief",
    "later": "park it; set a follow-up date, do not send anything now",
    "question": "draft an answer for a human to approve",
    "unclear": "read it yourself - the classifier would not guess",
}


def classify_reply(text: str, llm=None) -> dict:
    """Rule-first intent. The LLM only breaks ties the rules could not."""
    low = f" {(text or '').lower()} "
    for intent, words in INTENT_RULES:
        if any(w in low for w in words):
            return {"intent": intent, "confidence": 0.9 if intent != "question" else 0.5,
                    "next_action": INTENT_ACTION[intent], "by": "rules"}
    if llm is not None:
        try:
            guess = llm.classify_reply(text)
        except Exception:
            guess = None
        if isinstance(guess, dict) and guess.get("intent") in INTENT_ACTION:
            intent = guess["intent"]
            return {"intent": intent, "confidence": float(guess.get("confidence", 0.4)),
                    "next_action": INTENT_ACTION[intent], "by": "llm"}
    return {"intent": "unclear", "confidence": 0.0, "next_action": INTENT_ACTION["unclear"], "by": "rules"}

# Where creator data comes from, and what is in this repo

## What ships here

`data/creators.seed.json` - 24 creator records. They are **anonymised profiles derived from
real scouting work**, not scraped rows and not invented numbers pulled out of the air. Each
record is a structure Plugboard can score: audience size, median views, engagement rate,
posting cadence, topics, language, geography, price range, whether paid work and ad labels
are accepted, and one or two sourced facts.

What has been removed, deliberately and before anything was committed:

- names, handles, channel URLs, email addresses, phone numbers,
- anything that identifies a specific account, in any field, including the evidence text.

`display_label` is a description (`"ID TikTok - student money diaries"`), not an identity.
The `source_url` on each evidence item is a `local://scout/<date>/<id>` reference into the
operator's own scouting notes, which are not part of this repository.

A test (`test_contact_details_are_not_in_the_committed_index`) fails the build if an `@`
appears anywhere in the index.

## The contacts boundary

A creator record carries `contact_channel` (`email` / `dm` / `form`) and `contact_ref` (an
opaque key). The actual address lives in `data/contacts.local.json`, which is gitignored and
never committed:

```json
{ "c014": "someone@example.com" }
```

`catalog.resolve_contact()` is the only function that crosses that boundary, and it is
called at exactly one moment: constructing a sender for a draft a human has already
approved. A missing contacts file is normal, not an error - the whole pipeline, the demo
and the test suite all run without a single real address on disk.

## How a real index gets built

The shape of the file is the contract. Populating it is the operator's job, and the
ordering below is deliberate - cheapest and most reliable first.

1. **Self-reported, invited.** A creator fills in a form or sends a rate card. Best data,
   including price, and consent is explicit.
2. **Official public APIs and oEmbed.** YouTube Data API, TikTok/YouTube/Instagram oEmbed
   endpoints, public RSS for podcasts and newsletters. Public metrics, ToS-compliant,
   per-platform rate limits respected.
3. **Public pages, read-only, low rate.** Follower counts and recent post dates that a
   logged-out browser can see. Never behind a login, never behind a paywall, never a
   captcha - the hackathon brief disqualifies ToS violations and so does this project.
4. **Manual scout notes.** A human watches five recent posts and writes down what is
   actually true. This is where the `evidence` facts come from, and it is the reason the
   outreach can say something specific instead of "I love your content".

What is explicitly out of scope: buying scraped contact lists, harvesting emails from bio
links en masse, or anything that produces addresses of people who never asked to hear from
anyone. `RETOUCH_COOLDOWN_DAYS` and the blocklist exist because a list you can spam is a
list you will burn.

## Refresh and decay

Every evidence item carries `observed_at`, and every draft prints it inside the email
(`observed 2026-09-21`). This is not decoration: an email quoting a three-month-old fact is
worse than no email, and putting the date in the message makes stale data embarrassing
enough to fix.

Suggested cadence: metrics weekly, evidence facts before any outreach wave, price ranges
whenever a deal closes at a different number.

## The fields, and what they are for

| Field | Used by | Notes |
|---|---|---|
| `languages`, `geo`, `audience_age_band` | hard filter + `audience_fit` | Language mismatch is absolute |
| `topics` | `topic_fit` | Canonical slugs from `taxonomy.TOPICS` |
| `platforms[].median_views` | `reach_fit`, projections, CPM | Median, not best, not mean |
| `platforms[].engagement_rate` | `engagement_quality` | (likes+comments+shares)/views, 0..1 |
| `platforms[].followers` | authenticity check | Only used as a ratio against views |
| `cadence_per_week`, `days_since_last_post` | `freshness` | |
| `price_usd_min/max` | `budget_fit`, offer | Self-reported |
| `accepts_paid_promo`, `discloses_ads` | hard filters | Both must be true for a paid campaign |
| `safety_flags` | hard filter | Matched against the brief's exclusions |
| `evidence` | outreach | **No evidence, no draft** - `compose()` raises |

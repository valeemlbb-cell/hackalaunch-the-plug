# Matching methodology

This is the long version of the README's summary: what Plugboard scores, why those things,
and where it will be wrong. Everything described here lives in `plugboard/matching.py` and
`plugboard/taxonomy.py`, and every constant named below is a named constant in the code, not
a magic number buried in an expression.

## The shape of the answer

```
creators -> [hard filters] -> [7 weighted sub-scores] -> [portfolio diversification] -> picks
```

A creator that survives the filters gets seven scores between 0 and 1. Each one carries a
sentence written for a founder, not a log file. The weighted sum is the match score; the
sentences are the explanation. Nothing is learned and nothing is sampled, so the same
inputs always produce the same ranking, and a founder who disagrees with a placement can
point at the exact line that caused it.

## 1. Hard filters

A filter is for situations where the deal is impossible, not merely weak. Each returns a
string that is shown to the founder verbatim.

| Filter | Why it is absolute |
|---|---|
| on the blocklist | Someone said no or opted out. That is permanent, not a cooldown. |
| does not accept paid promotion | The campaign is paid; there is no deal to have. |
| does not label paid posts | Running an undisclosed ad is illegal in most of the markets this targets and is a disqualifier in the hackathon brief. |
| carries an excluded safety flag | The founder explicitly ruled out that category. |
| no shared language | A brief in Bahasa Indonesia and a creator posting only in English cannot serve each other. |
| authenticity check failed | See below. |

### The authenticity check

`median_views / followers < 0.008` excludes the creator outright with the numbers shown.
Below that ratio the audience is not watching, which in practice means bought followers or
a long-dead account with a big legacy count. The seed index contains one creator like this
(`c010`: 410,000 followers, 1,800 median views) so the behaviour is visible in the demo.

The opposite case - views far *above* the follower count - is **not** a filter. On TikTok
that is normal and often good. It becomes a *risk note* above a ratio of 3.0, telling the
founder to eyeball the last five posts before paying.

## 2. The seven sub-scores

| Dimension | Weight | What it measures |
|---|---|---|
| `topic_fit` | 0.26 | Does this audience care about the category at all |
| `audience_fit` | 0.18 | Language, geography, age band |
| `reach_fit` | 0.14 | Is the size right *for this goal* |
| `engagement_quality` | 0.12 | Do the viewers do anything |
| `freshness` | 0.10 | Posting now, not dormant |
| `budget_fit` | 0.12 | Affordable, and at what CPM |
| `platform_fit` | 0.08 | Active where the campaign runs |

The weights sum to exactly 1.0 and a test enforces it.

### topic_fit (0.26)

Campaign topics and creator topics are both canonical slugs from `taxonomy.TOPICS`. A brief
is mapped to slugs by whole-word phrase matching - `"ai"` must not fire on `"raid"`, and
`"car"` must not fire on `"care about"`, which is why the matcher is a bounded regex rather
than a substring test. A single trailing `s` is tolerated so `"signups"` hits `"signup"`.

Overlap is scored per campaign topic:

- same slug = 1.0
- a neighbour in `taxonomy.RELATED` = 0.5 (a crypto audience is a plausible fintech
  audience; it is not a plausible cooking audience)
- otherwise 0.0

Campaign topics are then weighted `1/(i+1)` by the order the founder mentioned them, so the
headline topic counts more than the fifth thing mentioned in passing.

**Why a curated vocabulary instead of embeddings.** Embeddings cover more words and produce
matches nobody can defend. The deliverable here is an *explanation*, and "cosine similarity
0.71" is not one. Adding a topic is a two-line edit in `taxonomy.py`, and the cost of the
approach is stated plainly in the limitations below.

### audience_fit (0.18)

Language match 0.45, geography 0.35, age band 0.20. `GLOBAL` satisfies any geography. A
`mixed` age band on either side is treated as compatible rather than penalised, because
unknown is not the same as wrong.

### reach_fit (0.14)

Every goal has a band of median views that historically performs for it:

| Goal | Band |
|---|---|
| awareness | 20,000 - 2,000,000 |
| app_installs | 8,000 - 500,000 |
| community | 5,000 - 300,000 |
| signups | 4,000 - 200,000 |
| sales | 3,000 - 150,000 |

Inside the band scores 1.0. Below the floor scales linearly. Above the ceiling takes a soft
penalty capped at 0.6, because reach still has value - it just costs more per outcome. This
is the dimension that stops "biggest account wins", which is the failure mode of every
spreadsheet this tool replaces.

### engagement_quality (0.12)

`engagement_rate / (goal target x 1.5)`, clamped to 1.0. Targets run from 2% for awareness
to 5.5% for sales: a campaign that needs people to act needs an audience that acts.

### freshness (0.10)

`0.7 x recency + 0.3 x cadence`. Recency is full marks within 7 days and zero at 60.
Cadence saturates at 3 posts a week. A creator quiet for more than 21 days also picks up a
risk note.

### budget_fit (0.12)

Starts from whether the asking price fits `budget_per_creator_usd`, then multiplies by
`target_cpm / implied_cpm` when the implied CPM is worse than the target. So a cheap
creator with terrible reach does not score well merely for being cheap.

`target_cpm_usd` is derived from the goal when the brief does not state one: $6 awareness,
$9 community, $12 signups, $14 app installs, $18 sales.

### platform_fit (0.08)

Fraction of the campaign's requested platforms the creator is actually on. Deliberately the
smallest weight: a strong creator on the wrong platform is usually worth a conversation,
and a weak one on the right platform is not.

## 3. Portfolio diversification

Ranking alone puts the whole budget in one topic cluster. `diversify()` caps picks at
`DIVERSITY_MAX_PER_TOPIC` (default 2) per primary topic, then backfills by score if the cap
leaves the list short - so it always returns `min(limit, eligible)` and never silently
under-delivers.

In the sample run this is what pulls a comedy creator and a web3 explainer into a personal
finance campaign: two audiences the founder would not have searched for, both adjacent
enough to score.

## Derived outputs

- **`suggested_offer_usd`** opens at the creator's own published floor, raised to 70% of the
  per-creator budget if that is higher, and capped by the budget. It never exceeds the
  budget; a test enforces it.
- **`projected_views_low/high`** is `median_views x [0.5, 1.6] x deliverable count`. It is a
  band, labelled an estimate everywhere it appears, including inside the outreach email.
  Presenting a single confident number would be inventing a metric.
- **`risks`** are the things a founder should check by hand before paying: view/follower
  anomalies, dormancy, price above budget, content flags, missing contact channel.

## Where this is wrong

- **Vocabulary coverage.** A product in a category not in `taxonomy.TOPICS` scores 0.35
  neutral on topic fit and says so. Real deployment means growing that file.
- **Self-reported rates.** `price_usd_min/max` comes from a rate card or a past deal. Rates
  move; the number can be stale.
- **Medians, not distributions.** A creator with one viral video and nine flops has the same
  median as a consistent one. Engagement rate partly compensates; it does not fully.
- **No audience overlap detection.** Two creators can serve substantially the same people.
  Topic diversification is a proxy, not a measurement.
- **Age band is coarse.** It comes from the scout's read, not from platform analytics the
  creator has not shared.

Each of these is a reason the final call belongs to a human, which is the same reason the
approval gate exists.

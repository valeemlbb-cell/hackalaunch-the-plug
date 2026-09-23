# Plugboard

**An AI marketing agent that takes a founder's brief, finds the creators who actually fit,
writes the outreach, waits for a human to say yes, and then tracks what the deal did.**

Submission for [The Plug](https://hackalaunch.com/h/the-plug) on HackaLaunch.

Finding the right creator still runs on cold DMs and spreadsheets. Plugboard replaces the
spreadsheet without replacing the person: it does the reading, the arithmetic and the
drafting, and it is structurally incapable of contacting anybody on its own.

```
brief -> match (with reasons) -> draft -> HUMAN APPROVES -> send -> reply -> deal -> results
```

Everything runs offline, on the standard library, with no API key and no account. Clone it,
run the commands below, and the whole loop works.

## Demo

**[demo_small.mp4](demo_small.mp4)** - 2 minutes 19 seconds, 720p, 2.4 MB, in this
repository. The 1080p master is attached to the [latest
release](https://github.com/valeemlbb-cell/hackalaunch-the-plug/releases) rather than
committed, so the repo does not carry two near-identical binaries.
Hosted copy: `<link added at submission time>`

**What the video is, exactly.** It is not a screen recording of somebody using the app. It
is *rendered* by `demo/make_demo.py` from real output: the script wipes a workspace, drives
the real CLI with `subprocess`, and types the **actual stdout** of those runs onto frames;
the dashboard shots are **real screenshots** of the real server taken with headless
Chromium; the voice-over is **synthesized** with the offline Windows speech engine. No
number, no ranking and no refusal in the video was written by hand - but the terminal you
see is a rendering of a real run, not a capture of one. Rebuild it yourself and compare:
`python demo/make_demo.py` (see [requirements-demo.txt](requirements-demo.txt); needs
`ffmpeg` on PATH).

---

## Run it in two minutes

Requires Python 3.11+. Nothing else.

```bash
git clone https://github.com/valeemlbb-cell/hackalaunch-the-plug.git && cd hackalaunch-the-plug
python -m pytest tests -q                     # 129 tests, ~86% coverage

python -m plugboard brief data/briefs/sample_brief.txt --id kilat
python -m plugboard match  --campaign kilat --limit 5 --show-excluded
python -m plugboard draft  --campaign kilat --limit 3
python -m plugboard queue
python -m plugboard show   d-kilat-c014
python -m plugboard approve d-kilat-c014 --by "your name"
python -m plugboard send    d-kilat-c014          # dry run: writes workspace/outbox/*.eml
python -m plugboard serve                         # dashboard on http://127.0.0.1:8799
```

Try `python -m plugboard send d-kilat-c002` *before* approving it. It refuses.

---

## The four things the brief asks for

### 1. Brief processing - prose to a structured campaign

`python -m plugboard brief data/briefs/sample_brief.txt --id kilat`

```
  product      Kilat
  goal         signups      KPIs: views, signups
  audience     id  geo ID  age 18-24
  topics       personal_finance, career
  platforms    tiktok, youtube
  budget       $3,000 total, $350/creator, target CPM $12.00
  deliverables 2 x short-form video, 1 x long-form video
  window       2026-10-01 -> 2026-10-21
```

Deterministic, offline, and it says what it could **not** find. A brief with no budget
prints `! budget_total_usd not found in the brief` rather than silently defaulting to zero -
a parser that guesses quietly is worse than one that guesses loudly.

Two parsing details worth the trouble: `"2 x TikTok"` does not become a Twitter campaign,
and `"we would rather not buy one big name"` does not turn a waitlist campaign into a sales
campaign, because goal words are counted inside goal-*declaring* sentences first.

### 2. Matching - with the reasoning attached

`python -m plugboard match --campaign kilat --limit 5 --show-excluded`

```
1. [A] 1.000  c014  ID TikTok - student money diaries
       topic_fit           0.260   exact topic overlap on career, personal_finance
       audience_fit        0.180   speaks id; based in ID, the campaign's market; audience age 18-24 fits
       reach_fit           0.140   52,000 median views on tiktok sits inside the signups band
       engagement_quality  0.120   8.8% engagement on tiktok against a 4.5% target for signups
       budget_fit          0.120   asks $120-$210, inside the $350/creator budget; implied CPM $4.04 vs target $12.00
       freshness           0.100   last posted 1d ago, about 4.5 posts/week
       platform_fit        0.080   active on tiktok, youtube
       evidence            weekly money-diary series on living in Jakarta on a student budget (observed 2026-09-21)
       offer               $244  projected 52,000-166,400 views (estimate)

Filtered out:
   x c008  carries a flag the brief excludes: gambling_content
   x c010  authenticity check failed: 1,800 median views against 410,000 followers (0.004 views/follower) - inflated audience
   x c011  does not accept paid promotion
   x c012  no shared language (campaign id, creator en)
   x c017  does not disclose paid posts - refused on advertising-disclosure grounds
```

Seven weighted dimensions summing to 1.0, each producing a sentence a founder can argue
with. Six hard filters that exclude rather than downrank, each stating its reason. Then a
portfolio pass that caps how many picks share a primary topic, so the budget does not all
land in one audience - that is what pulls a comedy creator and a web3 explainer into a
personal-finance campaign above a third budgeting account.

Nothing is learned and nothing is sampled: run it twice, get the same ranking.

Full methodology, every weight, every band, and a frank list of where it is wrong:
**[docs/MATCHING.md](docs/MATCHING.md)**.

### 3. Outreach - personalised, disclosed, and gated

`python -m plugboard draft --campaign kilat --limit 3` then `show`:

```
Halo kak,

Yang bikin aku kontak kamu: weekly money-diary series on living in Jakarta on a student
budget, 8.8% engagement at 52k median views (observed 2026-09-21).

Aku lagi bantu Kilat - a savings app for Indonesian workers in their first or second job.
Yang dicari: 2 x short-form video, 1 x long-form video, dan kayaknya audiens kamu cocok:
audiens kamu udah biasa sama konten keuangan pribadi, kerja dan karir; audiensnya 18-24 di
ID, persis yang kami cari.

Penawaran: $244 untuk ..., 2026-10-01 - 2026-10-21. Perkiraan jangkauan sekitar
52,000-166,400 views total - itu estimasi dari angka publik kamu, bukan target yang wajib
kekejar.

Ini kerja sama berbayar, jadi postingannya wajib ditandai iklan (#ad / label paid
partnership) di sisi kamu dan kami.
...
Kalau nggak cocok, bales 'nggak dulu' aja, aku nggak akan kirim lagi.
```

Written in the creator's language, opening with one **sourced, dated fact**. `compose()`
raises rather than returning a draft when the creator has no evidence on record - Plugboard
does not write "I love your content" emails. It also refuses to produce a paid pitch with no
ad-disclosure line, or any message with no opt-out line.

Replies are classified (`interested` / `rate_question` / `later` / `unsubscribe` /
`question`) and each intent has a declared next action. `unsubscribe` blocklists the creator
permanently, and the blocklist is re-checked at matching, at queueing, and again inside
`send()`.

### 4. Tracking - deliverables, deadlines, results

```bash
python -m plugboard deal open --campaign kilat --creator c014 --fee 260
python -m plugboard deal deliverable deal-kilat-c014 --desc "2 x TikTok short" --due 2026-10-05
python -m plugboard result deal-kilat-c014 --deliverable deal-kilat-c014-d1 \
    --platform tiktok --url https://... --views 74000 --clicks 1900 --conversions 210
python -m plugboard due --days 7
python -m plugboard report --campaign kilat
```

```
  committed spend    $260
  views              74,000
  blended CPM        $3.51
  cost / conversion  $1.24
  deliverables       1/2 done, 0 missed  (rate 50%)
  Every view figure above traces to a post URL recorded with `plugboard result`.
```

Deal status only moves along a declared transition table. Every result requires the URL of
the post it measures. CPM and cost-per-conversion are **derived** - there is no field
anywhere for typing in a performance number, because the brief disqualifies fake engagement
metrics and the cheapest way to honour that is to make the number impossible to fabricate.

---

## The part we actually care about: the approval gate

"A human approves outreach" is easy to claim. Here it is a signature:

```
approve()  token = HMAC-SHA256(workspace secret, draft_id + sha256(subject + body))
send()     recompute, compare, refuse on mismatch
```

Change one character of the message after approval and the send is refused, because the
approval was bound to that exact text - not to the draft's id. A bug, a careless edit, or a
prompt injection inside a creator's reply cannot forge a token: the secret is generated per
workspace, lives outside version control, and is never given to a model.

```bash
$ python -m plugboard send d-kilat-c014
refused: draft d-kilat-c014 is pending; a human must approve it first
```

Plus: dry run by default; at most 10 drafts staged per call; one approval per message; 25
sends a day; 20 seconds between sends; 30-day re-contact cooldown; no "approve all" button
anywhere. Full model in **[docs/SAFETY.md](docs/SAFETY.md)**.

---

## Dashboard

`python -m plugboard serve` - a four-column pipeline on `127.0.0.1:8799`: the parsed brief,
the explained matches, the approval gate, the deals. The approval column is the loudest
thing on the page because it is the only place a human decision is required. Approve /
reject / send call the same functions the CLI calls; there is no looser second path to a
send. Localhost-only by construction, CSRF token on every POST, everything escaped.

The tail of the append-only audit log sits under the pipeline: queued, approved by whom,
sent, refused and why.

---

## Optional: deal receipts on Solana devnet

```bash
python -m plugboard receipt anchor --deal deal-kilat-c014
python -m plugboard receipt verify --deal deal-kilat-c014
```

Hashes the agreed terms (fee, currency, deliverables, dates) and writes a single SPL Memo:
`plugboard:v1:<deal_id>:<sha256>`. A hash, not the parties and not the fee - anyone holding
the deal record can verify it, anyone holding only the transaction learns nothing. Change
the fee or add a deliverable and `verify` says the terms changed.

**Devnet only.** `SOLANA_CLUSTER=mainnet-beta` is refused at startup and re-checked before a
transaction is built. Nothing here moves value.

**Honest status - read this before judging the Solana part.** There is **no confirmed
devnet transaction to link yet.** The transaction builds, signs, and is accepted for
simulation by `api.devnet.solana.com`, but it has never been confirmed on chain from the
build machine: every airdrop request to the public devnet *and* testnet faucets was answered
with a rate-limit error, so the fee payer sits at 0 SOL. We would rather say that than link
a transaction we did not land.

Anything with a funded devnet key can finish it in two minutes, and the explorer URL it
prints belongs in this paragraph:

```bash
solana-keygen new -o devnet.json --no-bip39-passphrase
solana airdrop 1 -k devnet.json --url devnet      # or any devnet faucet
SOLANA_KEYPAIR_PATH=devnet.json python -m plugboard receipt anchor --deal deal-kilat-c014
```

`receipts.py` is the least-covered module in the suite (41%) for the same reason: the parts
that need a live RPC are the parts we could not exercise. Everything up to the signature -
canonical terms, hashing, memo construction, mainnet refusal, `verify` - is covered and
tested offline.

Without a funded key, `anchor` reports `not anchored: <reason>` and still stores the hash -
the hash is the product, the chain is a witness.

---

## Tests

```bash
python -m pytest tests -q --cov=plugboard --cov-report=term-missing
```

129 tests, 86% line coverage. Core modules: brief 96%, tracking 95%, models 94%, matching
92%, CLI 92%, ui 92%, store 86%, web 86%, approval 84%. The uncovered remainder is mostly
live network code - the SMTP transport, the RPC calls, and the LLM HTTP adapters - which is
also the code that does nothing in a default run.

The tests that matter most are in `tests/test_approval.py`: sending without approval, body
tampering, subject tampering, forged tokens, editing after approval, opting out after
approval, oversized batches, and the audit trail.

`tests/test_cli_end_to_end.py` drives the whole pipeline through the real CLI, and
`tests/test_dashboard.py` starts the real server and checks the gate holds through the web
path too.

---

## Project layout

```
plugboard/
  brief.py      prose -> Campaign (deterministic; LLM may only fill blanks)
  taxonomy.py   the shared vocabulary both sides are mapped into
  matching.py   hard filters, 7 weighted sub-scores, portfolio diversification
  outreach.py   draft composition, safety validation, reply classification
  approval.py   the HMAC-signed human gate
  senders.py    dry-run and SMTP; the only code that can open a socket
  tracking.py   deals, deliverables, deadlines, measured results
  receipts.py   canonical terms hash + optional devnet memo anchor
  store.py      atomic flat-file store + append-only audit log
  web.py, ui.py localhost dashboard
  cli.py        every command above
data/
  creators.seed.json   24 anonymised creator records
  briefs/sample_brief.txt
docs/
  MATCHING.md   the methodology, in full, including its limitations
  DATA_SOURCES.md  where creator data comes from and what was stripped
  SAFETY.md     every control, and the test that proves it
```

---

## Data, privacy, and what was reused

**The creator index is anonymised.** `data/creators.seed.json` holds 24 records derived from
real scouting work with every identifier removed: no names, no handles, no URLs, no
addresses. `display_label` is a description, not an identity. A test fails the build if an
`@` appears in the file. One consequence to expect before you click: the `source_url` on
every evidence item is a `local://scout/<date>/<id>` reference into private scouting notes,
not a public link, because publishing the link would re-identify the creator the
anonymisation just removed. Contact details live in `data/contacts.local.json`, gitignored and
absent from this repo; `catalog.resolve_contact()` is the only bridge, and it is called only
when constructing a sender for an already-approved draft. Details:
**[docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)**.

**Pre-hackathon work.** The hackathon rules require this to be stated plainly.

Plugboard's code was written for this hackathon. Its *design* is a rewrite of an internal
system the team has been running since 2026-09 for a small clip-production business: demand
scouts that find who needs distribution, a mail engine with a human action queue, and a
tracker that pulls public post metrics. That system produced a real client (a podcast pilot
agreed on 2026-09-13), which is where the outreach format - one sourced fact, a concrete
offer, a free sample, an easy no - comes from.

What was carried over: the *shape* of the loop and the message format, both re-implemented
here from scratch. What was **not** carried over: no code, no client data, no contact lists,
no leads, no credentials. The approval-token scheme, the scoring engine, the taxonomy, the
tracking model, the dashboard, the receipts and the tests are new and specific to this
submission.

**AI-agent usage disclosure.** This project was built with Claude Code (Claude Opus) as the
coding agent, on a human operator's direction, as the hackathon requires. The agent wrote
the implementation and the tests; the operator set the architecture, the safety
requirements, and reviewed the result. The rule that the agent is not allowed to send
anything applies at runtime too: an agent can draft all day here and still cannot produce a
valid approval token.

## Licence

MIT - see [LICENSE](LICENSE).

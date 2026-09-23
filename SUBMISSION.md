<!-- generated-header v2 -->
# SUBMISSION — the-plug

Paste-ready. Five fields, in the order the HackaLaunch form asks for them.
Refreshed 2026-09-24T05:06:10+07:00.

---

## TITLE  (70/80 chars)

```
Plugboard — an AI marketing agent that never sends outreach on its own
```

## DESCRIPTION  (1490 chars)

```
Plugboard takes a founder's brief, finds the creators who actually fit, writes the outreach, waits for a human to say yes, and then tracks what the deal did.

What it does: brief → match with reasons → draft → HUMAN APPROVES → send → reply → deal → results. It replaces the spreadsheet without replacing the person: it does the reading, the arithmetic and the drafting, and it is structurally incapable of contacting anybody on its own.

How it works: matching scores creators against the brief on audience fit, engagement quality, price band and past performance, and every ranking prints the reasons behind it, including the reasons a creator was rejected. Drafts are generated per creator and land in an approval queue. Nothing leaves the queue without an explicit human approval — the send path refuses an unapproved draft, so the gate is in the execution path rather than in a prompt. The demo video shows that refusal happening. After a deal is agreed, results are tracked back against the original brief.

Real vs mocked: the pipeline, the scoring, the approval gate and the dashboard are real and run on the Python standard library with no API key, no account and no network. The creator roster and the reply traffic are a local fixture dataset — no personal data is scraped and no message is sent anywhere. That is a deliberate constraint, not a missing feature.

How to run: Python 3.11+, `python -m pytest tests -q` (129 tests, ~86% coverage), then the CLI walkthrough in RUN.md.
```

## REPO URL

```
https://github.com/valeemlbb-cell/hackalaunch-the-plug
```

## VIDEO URL

```
VIDEO_URL_PENDING
```

> The main session posts `demo_x.mp4` from this folder to X and replaces the
> line above with the public post URL. The form needs a **link**; a file is useless.

## SOLANA PAYOUT ADDRESS

```
7W31iaCmjerN1jkpEnmZevn74SZxv83yEQvLsnc4PS7Q
```

---

## Appendix — earlier submission notes (kept verbatim)

# HackaLaunch submission - The Plug

**Project name:** Plugboard
**Hackathon:** The Plug (https://hackalaunch.com/h/the-plug)
**Team:** Warung Ops - Henggar (X [@issue0x](https://x.com/issue0x), Telegram @sambobolo)
**Repo URL:** https://github.com/valeemlbb-cell/hackalaunch-the-plug
**Demo video:** `<VIDEO URL>` - **the one remaining human step.** Upload `demo.mp4` (1080p,
2:19) to YouTube unlisted / Loom / Vimeo / X as the rules require, then replace this token
here, in the paste block below, and in the README's "Hosted copy" line. See [RUN.md](RUN.md) §3.
**Payout address (Solana):** `7W31iaCmjerN1jkpEnmZevn74SZxv83yEQvLsnc4PS7Q`
**Licence:** MIT

---

## One-paragraph description

Plugboard is an AI marketing agent that turns a founder's paragraph into a ranked shortlist
of creators, drafts the outreach, tracks the deals that result - and cannot send a single
message on its own. Approval is a cryptographic act: approving signs an HMAC over the exact
subject and body, and `send()` recomputes it before anything leaves the machine, so editing
one character after approval - whether by a bug or by a prompt injection hidden in a
creator's reply - kills the send. Matching is deterministic and explains itself: seven
weighted dimensions summing to 1.0, six hard filters that exclude rather than downrank, and
a sentence of reasoning a founder can argue with on every line. Deal terms can optionally be
anchored as a hash in an SPL Memo on Solana devnet (built and signed; not yet confirmed on
chain - the README says why, in the open). Everything else follows from those two
choices - no "approve all" button, no field for typing a performance number, no handles or
addresses in the repo.

---

## What was built during the hackathon vs before

**Built during the hackathon (all code in this repo):** the entire implementation. The
approval-token scheme, the seven-dimension scoring engine and its six hard filters, the
topic taxonomy, the outreach drafting and validation layer, the reply classifier, the deal
state machine and tracking model, the localhost dashboard, the Solana devnet receipts, the
anonymised seed index, the docs, and all 129 tests.

**Pre-hackathon (design lineage only, stated in the README as the rules require):** the
*shape* of the loop and the message format come from an internal system the team has run
since 2026-09 for a small clip-production business - demand scouts, a mail engine with a
human action queue, and a metrics tracker. That system produced a real client (a podcast
pilot agreed 2026-09-13), which is where the outreach format comes from: one sourced fact, a
concrete offer, a free sample, an easy no.

**Not carried over:** no code, no client data, no contact lists, no leads, no credentials.
Both the lineage and the boundary are stated in [README.md](README.md#data-privacy-and-what-was-reused).

**AI-agent usage:** built with Claude Code (Claude Opus) as the coding agent on a human
operator's direction. The operator set the architecture, the safety requirements, and
reviewed the result.

---

## How it meets every requirement, point by point

### 1. Brief processing - prose in, structured campaign out
A founder's paragraph is parsed into goal, audience, budget, per-creator budget, target CPM,
deliverables, dates and exclusions. Deterministic and fully offline - no API key needed to
run the demo. It **reports what it could not parse** rather than silently defaulting a
missing budget to zero. `plugboard brief` - README §1.

### 2. Creator matching - with the reasoning attached
Seven weighted dimensions summing to exactly 1.0 (topic fit, audience fit, reach fit *for
that specific goal*, engagement quality, freshness, budget fit, platform fit). Each writes a
human sentence: *"96,000 median views on tiktok sits inside the signups band."* Six hard
filters exclude and say why - a safety flag the brief ruled out, a creator who never labels
paid posts, a language mismatch, and an authenticity check that drops an account with
410,000 followers but 1,800 median views. A portfolio pass caps how much budget lands in one
topic. Nothing is sampled or learned: same inputs, same ranking, every run. Methodology and
its stated limitations: [docs/MATCHING.md](docs/MATCHING.md). `plugboard match` - README §2.

### 3. Outreach - personalised, disclosed, and gated
Drafts open with one **sourced, dated** fact and are written in the creator's language. A
creator with no evidence on record gets **no email at all** - Plugboard raises rather than
writing "I love your content". Every paid pitch carries an ad disclosure and every message
carries an opt-out; validation refuses a draft missing either. Replies are classified, and
"no thanks" blocklists that creator permanently. `plugboard draft` / `reply` - README §3.

### 4. Deal tracking - deliverables, deadlines, results
Deals move along a declared state table; illegal transitions are rejected. Every recorded
result **requires the URL of the post it measures** - CPM, cost per conversion and delivery
rate are derived, and there is no field for typing in a performance number. An append-only
audit trail records every state change. `plugboard result` / `report` - README §4.

### 5. Human-in-the-loop approval (the core of the submission)
Approving signs an HMAC over the exact subject and body. `send()` recomputes and compares.
**In the demo, one line is appended to an already-approved message while the token is left
untouched - and the send is refused**, because the approval was bound to the text and not to
the draft. The secret is generated per workspace, lives outside version control, and is
never given to a model, so an agent cannot forge a token. Sending is **dry run by default**
and there is no "approve all" button anywhere. README §"The approval gate".

### 6. Solana integration
Agreed terms are hashed and can be anchored as an SPL Memo on **devnet**: a hash only - not
the parties, not the fee. `plugboard verify` detects changed terms. Mainnet is **refused at
startup**. Optional; the rest of the product runs without it. README §"Deal receipts".

**Stated plainly: there is no confirmed devnet transaction to link.** The transaction
builds, signs and simulates against `api.devnet.solana.com`, but the public devnet *and*
testnet faucets rate-limited every airdrop from the build machine, so the fee payer never
had the lamports to land it. The README carries the same admission and the three commands
that finish it from a funded key. Judge this section on the code, not on a link.

### 7. Hackathon rules compliance
Public repo with full history; MIT licence; demo under 3 minutes (2:19) - **rendered** by
`demo/make_demo.py` from the real CLI's actual stdout and real screenshots of the real
dashboard, with synthesized narration, rather than a screen capture of a person using the
app; **no private keys, seed phrases or API keys**
anywhere - `.env.example` only; devnet only; no admin backdoors; no unsolicited bulk
outreach (the approval gate makes it structurally impossible); pre-hackathon work marked in
the README; 129 tests at 86% line coverage, including body tampering, subject tampering,
forged tokens, opt-out-after-approval and CSRF.

---

## Paste block for the HackaLaunch description field

Fill `<VIDEO URL>` first (the repo URL is already filled), then paste everything between
the rules.

---

**Plugboard - an AI marketing agent that cannot message anyone on its own.**

Repo: https://github.com/valeemlbb-cell/hackalaunch-the-plug
Demo (2:19): <VIDEO URL>
Payout: 7W31iaCmjerN1jkpEnmZevn74SZxv83yEQvLsnc4PS7Q

Finding the right creator still runs on cold DMs and spreadsheets. Plugboard does the
reading, the arithmetic and the drafting - and then stops, because the person, not the
agent, decides who gets contacted.

**Brief to campaign.** A founder's paragraph becomes structured: goal, audience, budget,
per-creator budget, target CPM, deliverables, dates, exclusions. Deterministic, offline, no
API key. It reports what it could not parse instead of defaulting a missing budget to zero.

**Matching, with the reasoning attached.** Seven weighted dimensions that sum to 1.0 -
topic fit, audience fit, reach fit *for that specific goal*, engagement quality, freshness,
budget fit, platform fit - and each one writes a sentence a founder can argue with
("96,000 median views on tiktok sits inside the signups band"). Six hard filters exclude
rather than downrank and say why: a safety flag the brief ruled out, a creator who never
labels paid posts, a language mismatch, and an authenticity check that drops an account
with 410,000 followers and 1,800 median views. A portfolio pass then caps how much of the
budget lands in one topic. Nothing is learned and nothing is sampled: same inputs, same
ranking, every time. Full methodology and its limitations: docs/MATCHING.md.

**Outreach that earns the send.** Drafts are written in the creator's language and open
with one sourced, dated fact. A creator with no evidence on record gets no email at all -
Plugboard raises rather than writing "I love your content". Every paid pitch carries an ad
disclosure and every message carries an opt-out; validation refuses a draft without them.
Replies are classified, and "no thanks" blocklists that creator permanently.

**The approval gate is cryptographic, not procedural.** Approving signs an HMAC over the
exact subject and body. `send()` recomputes and compares. In the demo, something appends a
single line to an already-approved message while leaving the token untouched - and the send
is refused, because the approval was bound to the text, not to the draft. A bug, or a
prompt injection inside a creator's reply, cannot forge that token: the secret is generated
per workspace, lives outside version control, and is never given to a model. Sending is dry
run by default; there is no "approve all" button anywhere.

**Tracking that cannot be faked.** Deals move along a declared state table. Every recorded
result requires the URL of the post it measures. CPM, cost per conversion and delivery rate
are derived - there is no field for typing in a performance number.

**Optional Solana receipts.** The agreed terms are hashed and can be anchored as an SPL
Memo on devnet: a hash, not the parties and not the fee. Change the terms and `verify` says
so. Mainnet is refused at startup. In the open: the memo transaction builds, signs and
simulates, but it was never confirmed on chain - the public faucets rate-limited every
airdrop and the fee payer stayed at 0 SOL. The README says so too, with the commands that
finish it.

**On the creator data.** The 24-record seed index is anonymised - no names, handles, URLs
or addresses, and a test fails the build if an `@` appears in it. So each evidence item's
`source_url` is a `local://scout/<date>/<id>` pointer into private scouting notes, not a
clickable link: publishing the link would undo the anonymisation. See docs/DATA_SOURCES.md.

Also included: a localhost dashboard where the approval column is the loudest thing on the
page, an append-only audit trail of every state change, 129 tests at 86% line coverage
(including body tampering, subject tampering, forged tokens, opt-out-after-approval and
CSRF), an anonymised 24-creator seed index with no handles or addresses anywhere, MIT
licence, and `.env.example` only - no secrets in the repo.

Built with Claude Code as the coding agent, on a human operator's direction. Design lineage
and what counts as pre-hackathon work are stated plainly in the README.

---

## Submission checklist

- [x] Public repo live: https://github.com/valeemlbb-cell/hackalaunch-the-plug (full history, MIT)
- [x] Demo video ≤ 3 min built from real runs - `demo_small.mp4` (720p, 2.4 MB) in the repo, 1080p `demo.mp4` for the release
- [x] Description written (paste block above), repo URL filled in
- [x] Payout address included: `7W31iaCmjerN1jkpEnmZevn74SZxv83yEQvLsnc4PS7Q`
- [x] MIT licence, no secrets, devnet only, pre-hackathon work marked, CI runs the tests
- [ ] Verify the pushed tree matches local HEAD - **human step**, [RUN.md](RUN.md) §2
- [ ] Video uploaded to a hosted platform and `<VIDEO URL>` filled in here, in the paste block, and in the README - **human step**
- [ ] 1080p `demo.mp4` attached to a GitHub release - **human step**, [RUN.md](RUN.md) §3
- [ ] *(optional, improves the Solana section)* fund a devnet key and anchor one receipt, paste the explorer URL into the README - **human step**, [RUN.md](RUN.md) §5
- [ ] Submitted on HackaLaunch - **human step**, dashboard button `hacka-the-plug`

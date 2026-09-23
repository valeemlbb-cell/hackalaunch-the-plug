# HackaLaunch submission - The Plug

**Project name:** Plugboard
**Hackathon:** The Plug (https://hackalaunch.com/h/the-plug)
**Team:** Warung Ops - Henggar (X [@issue0x](https://x.com/issue0x), Telegram @sambobolo)
**Repo URL:** `<REPO URL>` *(fill after `gh repo create` - see [RUN.md](RUN.md))*
**Demo video:** `<VIDEO URL>` *(fill after upload - `demo.mp4`, 1080p, 2:19)*
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
anchored as a hash in an SPL Memo on Solana devnet. Everything else follows from those two
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

### 7. Hackathon rules compliance
Public repo with full history; MIT licence; demo under 3 minutes (2:19, 1080p, real screen
capture of real runs with English voice-over); **no private keys, seed phrases or API keys**
anywhere - `.env.example` only; devnet only; no admin backdoors; no unsolicited bulk
outreach (the approval gate makes it structurally impossible); pre-hackathon work marked in
the README; 129 tests at 86% line coverage, including body tampering, subject tampering,
forged tokens, opt-out-after-approval and CSRF.

---

## Paste block for the HackaLaunch description field

Fill the two placeholders first, then paste everything between the rules.

---

**Plugboard - an AI marketing agent that cannot message anyone on its own.**

Repo: <REPO URL>
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
so. Mainnet is refused at startup.

Also included: a localhost dashboard where the approval column is the loudest thing on the
page, an append-only audit trail of every state change, 129 tests at 86% line coverage
(including body tampering, subject tampering, forged tokens, opt-out-after-approval and
CSRF), an anonymised 24-creator seed index with no handles or addresses anywhere, MIT
licence, and `.env.example` only - no secrets in the repo.

Built with Claude Code as the coding agent, on a human operator's direction. Design lineage
and what counts as pre-hackathon work are stated plainly in the README.

---

## Submission checklist

- [x] Public GitHub repo prepared locally with full commit history (`RUN.md` has the exact `gh repo create` command)
- [x] Demo video ≤ 3 min recorded from real runs - `demo.mp4` (1080p, 2:19) and `demo_small.mp4` (720p, 2.4 MB)
- [x] Description written (paste block above)
- [x] Payout address included: `7W31iaCmjerN1jkpEnmZevn74SZxv83yEQvLsnc4PS7Q`
- [x] MIT licence, no secrets, devnet only, pre-hackathon work marked
- [ ] Repo pushed - **human step**, see [RUN.md](RUN.md)
- [ ] Video uploaded and URL filled in - **human step**
- [ ] Submitted on HackaLaunch - **human step**, dashboard button `hacka-the-plug`

# Submission text

Paste the block below into the HackaLaunch description field for **The Plug**. Fill the two
placeholders first.

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

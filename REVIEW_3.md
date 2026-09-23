# REVIEW_3 — Judge 3 (token-holder perspective)

Date: 2026-09-24 · Reviewer: independent audit agent · Score: **82 / 100**

## What I checked
- Re-read the hackathon page (hackalaunch.com/h/the-plug): 4-stage agent (brief → match w/
  explanations → outreach → deal tracking), public repo + README covering methodology/data
  sources/APIs, demo ≤ 3 min, description, human approval on outreach, `.env.example` with no
  creds, AI coding agent mandated, Solana **optional** (their suggestion: on-chain deals /
  escrow released on delivery). Pool $10.3K (90.087 SOL), winner by 24h token-weighted vote.
- Ran `python -m pytest tests -q` → **129 passed**.
- `git ls-files` → 47 files, clean tree, no `.env`, no `contacts.local`, no keypair,
  `demo_build/` excluded. LICENSE = MIT.
- `ffprobe demo.mp4` → 1920x1080, **138.9 s (2:19)**, h264 + aac, 3.0 MB. Under the cap.
- Read README.md, SUBMISSION.md, RUN.md.

## Would I vote for it?
Over a typical submission — yes. Every stated requirement is met and provable in a clone, the
tests actually run, and the approval gate is a real mechanism (HMAC over subject+body,
recomputed in `send()`) rather than a checkbox. That directly answers the platform's own
disqualifier list (unsolicited bulk outreach, fake metrics, missing disclosure) instead of
ignoring it. As a holder I'd rank it top-quartile.

But the vote is **24 hours, token-weighted, by people skimming**. On that axis the packet
underperforms its engineering, and two things would cost it real weight:

1. **The Solana section admits it never landed on chain.** README: "not confirmed on chain …
   faucet returned HTTP 429 … fee payer at 0 SOL". On a Solana-native platform that is the
   single line a rival voter screenshots. It is also a 2-minute fix (RUN.md §5 already has the
   commands). Worse, the memo-hash design ignores the angle the hackathon page itself names —
   *escrow released on delivery* — so the chain use reads as decorative even when funded.
2. **Nothing visual above the fold.** README has zero images (`grep '!\['` → no matches); it
   is ~14 KB of prose before a skimmer sees anything. The best asset in the whole packet — the
   send being refused after a one-line edit to an approved message — exists only inside a
   video the voter has to choose to play.

Minor: no hosted demo URL (`<VIDEO URL>` / `<REPO URL>` still placeholders, correctly left to
the human), and the README's "APIs used" obligation is satisfied mostly by "no APIs, offline",
which is true and defensible but should be stated as a *claim* at the top, not inferred.

## Single change that would most raise its odds
**Fund a devnet key, anchor a real receipt, and put the explorer link in the first screen of
the README** — replacing the "honest status" paragraph with a live transaction. It deletes the
only quotable weakness, converts an optional feature into a verifiable artifact a holder can
click, and costs two minutes of human time. Keep the honesty note about faucet limits one line
lower; do not delete it.

## Concrete fixes (ranked)
1. Run RUN.md §5 (`solana-keygen` → `airdrop` → `receipt anchor`), paste the explorer URL into
   README §"Deal receipts" and into SUBMISSION.md; delete the 0-SOL paragraph's lede.
2. Add a hero GIF (6–10 s, ≤ 3 MB) at the very top of the README showing: approved draft →
   one line appended → `send` refused. Frames already exist in `demo_build/frames/` and
   `demo_build/check/tamper.png`. This is the whole pitch in one loop.
3. Add a 5-line "What this is" block above the current opening prose: one sentence, the four
   commands, the refusal line, the video link. Move the long prose below it.
4. Add a second screenshot of the dashboard (approval column) — the packet claims a UI and
   never shows one to a non-player.
5. Sketch escrow explicitly, even if unimplemented: a 4-line "Why memo and not escrow (yet)"
   note in `docs/` naming the delivery-release flow. Pre-empts "they ignored the brief's
   Solana idea".
6. Upload `demo_small.mp4` (720p, 2.4 MB) as the hosted copy and fill both placeholders before
   submitting; a raw `.mp4` in a repo is not a demo link a voter will open.
7. In SUBMISSION.md's paste block, lead with the refusal demo sentence — currently it is the
   fourth bold heading; it is the only claim competitors cannot copy.

## Not problems (checked, fine as-is)
- Pre-hackathon lineage is disclosed clearly and the boundary (no code/data/contacts carried
  over) is explicit — meets the marking rule without over-claiming.
- Anonymised seed index, gitignored contacts, no handles or addresses.
- Mainnet refused at startup; dry-run default; no "approve all"; rate limits documented.
- Video length, resolution and authenticity (real CLI capture, rebuildable) are solid.

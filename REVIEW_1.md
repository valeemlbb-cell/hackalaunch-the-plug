# REVIEW_1 — hostile judge audit of "the-plug" packet (Plugboard)

Reviewed 2026-09-24. Scope: read-only audit of D:\warung-ops\hacka\the-plug.
Verdict: **no disqualifier found.** Score **88/100**.

## Disqualifier checklist

| Check | Result |
|---|---|
| Secrets in repo | PASS — `git ls-files` clean; only `.env.example` (all values blank); `workspace/`, `.env`, `data/contacts.local.json`, `demo_build/` gitignored; grep for keys/seed phrases/keypair arrays found nothing |
| `.env.example` present | PASS — present, documented, no real values |
| Mainnet money | PASS — `plugboard/config.py` refuses any non-devnet/testnet/localnet cluster at startup |
| Fake / non-functional demo | PASS on function — 129 tests pass, 86% line coverage, verified locally. See overclaim O-2 below |
| Demo length | PASS — 138.9 s (2:19), 1920x1080, under the 3-minute cap |
| Licence | PASS — MIT, © Warung Ops |
| Unlicensed assets | PASS — fonts are DejaVu (bundled with matplotlib, permissive); TTS is offline Windows System.Speech; no third-party media |
| Plagiarism | PASS — full local history, three authored commits, pre-hackathon lineage explicitly declared in README + SUBMISSION.md ("design lineage only, no code/data/contacts carried over") |
| Admin backdoor | PASS — dashboard refuses to bind off-localhost, per-process CSRF token, no "approve all", no god-mode flag found |
| Human-approval gate | PASS — HMAC over `draft_id:hash(subject,body)`; `send()` re-verifies; edit revokes; opt-out re-checked after approval; per-run queue cap 10, daily cap, inter-send delay |
| PII in data | PASS — anonymised 24-creator index, a test fails the build if `@` appears in it |

## Findings (ranked)

**H-1 — Solana integration is not demonstrably on-chain.** README states honestly that the
tx builds and signs but was never confirmed because the devnet faucet returned 429, so the
fee payer has 0 SOL. A judge scoring a "Solana integration" line item has nothing to click.
Biggest single point loss. Fix: fund a devnet key, run `plugboard receipt anchor --deal
deal-kilat-c014`, paste the explorer URL into README §Deal receipts and into SUBMISSION.md,
and replace the "honest status" paragraph. (RUN.md §5 already has the commands.)

**H-2 — Demo is described as something it is not.** SUBMISSION.md §7 says "real screen
capture of real runs with English voice-over". `demo/make_demo.py` renders Pillow terminal
frames from captured CLI stdout plus headless-Chromium dashboard screenshots, with
synthesized TTS. The *content* is real output, so this is an overclaim, not a fake — but a
hostile judge who opens `make_demo.py` will call it one. Fix: reword to "rendered from the
real CLI's actual stdout and real dashboard screenshots, synthesized narration", in
SUBMISSION.md and in the video's own closing frame if it repeats the claim.

**H-3 — Repo identity is inconsistent, and the repo is already pushed.** `git remote -v`
points at `https://github.com/valeemlbb-cell/hackalaunch-the-plug.git` and
`refs/remotes/origin/main` records an `update by push` at 03:22, yet RUN.md still instructs
the human to run `gh repo create warung-ops/plugboard --public --source=. --push`, which
will fail or create a second repo. SUBMISSION.md still carries `<REPO URL>` and
`<VIDEO URL>` placeholders. Fix: decide the canonical repo, rewrite RUN.md §2 to match
reality (verify public + README renders + `contacts.local.json` absent), and fill both
placeholders. Separately flag to the operator: the push was performed despite the standing
"agents never push to GitHub" rule — confirm the pushed tree is the one you want public.

**M-4 — Evidence `source_url` values are all `local://scout/<date>/<id>` (28 of them).** The
description sells "one sourced, dated fact"; a judge clicking a source gets a scheme that
resolves to nothing. docs/DATA_SOURCES.md explains this well, but the README/description do
not. Fix: one clause in the description — "seed index is anonymised, sources are references
into private scouting notes (docs/DATA_SOURCES.md)" — so the judge meets the caveat before
the data.

**M-5 — Both `demo.mp4` (3.0 MB) and `demo_small.mp4` (2.4 MB) are committed**, near-identical
content. Fix: keep one in-repo (the 720p), attach the 1080p to a GitHub release.

**L-6 — Demo-build dependencies are undeclared.** `make_demo.py` needs pillow, playwright,
matplotlib and ffmpeg; `requirements.txt` lists only pytest/pytest-cov/solders. Fix: add a
`requirements-demo.txt` or a commented block, so "rebuild the video" is reproducible.

**L-7 — `.coverage` and `.pytest_cache/` exist in the working tree** (gitignored, untracked).
Harmless, but delete before the human eyeballs `git status`.

## Scoring

- Compliance and safety posture: 38/40 — the approval gate is the strongest thing here and
  it is genuinely enforced in code, not prose.
- Requirement coverage (brief / match / outreach / tracking / Solana): 27/32 — all five
  present, Solana unproven (H-1).
- Evidence quality (tests, docs, reproducibility): 14/16 — 129 tests, 86%, three solid docs.
- Presentation honesty and submission readiness: 9/12 — H-2, H-3, M-4.

**Total 88/100.** Fixing H-1, H-2 and H-3 puts this in the mid-90s.

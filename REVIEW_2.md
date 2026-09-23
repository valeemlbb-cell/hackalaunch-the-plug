# REVIEW_2 — deliverables checklist audit (the-plug / Plugboard)

Auditor: Judge 2 (deliverables checklist). Date: 2026-09-24. Score: **88/100**.
Verdict: not disqualifying. Every hard rule is satisfied; the gaps are submission-form
artefacts (hosted video, filled URLs) and stale instructions, not missing product.

## Verified by running / fetching

| Requirement (hackalaunch.com/h/the-plug) | Status | Evidence |
|---|---|---|
| Public GitHub repo | PASS — already live | `https://github.com/valeemlbb-cell/hackalaunch-the-plug` returns 200, API `"private": false`, tree matches local HEAD `7d3a83d` |
| README: how to run | PASS | quickstart, Python 3.11+, stdlib only |
| README: how matching works | PASS | README §2 + `docs/MATCHING.md` with weights and stated limitations |
| README: data sources / APIs | PASS | `docs/DATA_SOURCES.md`, linked from README |
| Demo video ≤ 3 min | PASS on length, FAIL on hosting | `ffprobe` = 138.86 s (2:19), 1080p, 3.0 MB; also `demo_small.mp4` 2.4 MB. Rules require YouTube/Loom/Vimeo/X — no hosted link exists |
| Demo shows the whole workflow | PASS | `demo/make_demo.py` drives the real CLI via subprocess and screenshots the real dashboard |
| Short description | PASS | `SUBMISSION.md` paste block |
| Human approves outreach | PASS (strong) | HMAC over draft_id + sha256(subject+body), recomputed in `send()`; dry-run default; no approve-all |
| No keys/tokens/scraped PII in repo | PASS | `git ls-files` grep for `.env`/contacts/keypair/secret returns nothing; `.env.example` only; seed index anonymised |
| Tests actually run and pass | PASS | `python -m pytest tests -q --cov=plugboard` → 129 passed, 86 % total coverage, on Python 3.14 |
| Devnet only, mainnet refused | PASS | `config.py` refuses `mainnet-beta`; memo program `MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr` |
| Pre-hackathon work marked | PASS | README "Data, privacy, and what was reused" + SUBMISSION.md section; lineage vs carried-over stated |
| AI coding agent used + disclosed | PASS | README AI-agent disclosure |
| MIT licence | PASS | `LICENSE` present, detected by GitHub API |
| No admin backdoor / bulk unsolicited send | PASS | rate limits, cooldown, blocklist rechecked in `send()` |
| Working tree clean, full history | PASS | `git status` clean, 3 commits |

## Concrete fixes, in priority order

1. **Host the demo video and fill the link.** The rules name YouTube/Loom/Vimeo/X; a
   committed `.mp4` alone does not satisfy them. Upload `demo_small.mp4` (unlisted YouTube),
   then replace `Hosted copy: <link added at submission time>` in README.md and
   `<VIDEO URL>` in SUBMISSION.md (two places: header and paste block). **Blocking for
   submission.**
2. **Fill the repo URL.** `<REPO URL>` in SUBMISSION.md (header + paste block) and
   `git clone <this repo>` in README.md are still placeholders even though the repo is
   public. Use the real URL above. **Blocking for submission.**
3. **RUN.md is stale and will cause a duplicate repo.** §2 tells the owner to run
   `gh repo create warung-ops/plugboard --public --source=. --push`, but `origin` is already
   `valeemlbb-cell/hackalaunch-the-plug` and the push has happened (`.git/logs/refs/remotes/origin/main`
   = "update by push"). Rewrite §2 as "already published at <URL>; to publish updates run
   `git push origin main`", and keep the `gh repo create` line only as a fallback. Also flip
   the stale SUBMISSION.md checklist line "prepared locally" → pushed.
4. **Fix the "real screen capture" claim.** SUBMISSION.md §7 says the demo is a "real screen
   capture of real runs". `demo/make_demo.py` captures real CLI stdout and a real headless
   Chromium screenshot but re-renders terminal output into frames. Say "real CLI output and a
   real dashboard screenshot, rendered to video" — accurate and still strong. Judges penalise
   overclaiming harder than they reward polish.
5. **Land one real devnet transaction before the deadline.** `receipts.py` is 41 % covered
   and has never completed on chain; the README's "honest status" paragraph is the one place
   the packet reads as unfinished. RUN.md §5 is a two-minute fix — fund a devnet key, run
   `receipt anchor`, paste the explorer URL into README, push. Do not commit `devnet.json`.
6. **Add a minimal CI badge / workflow** (`.github/workflows/tests.yml` running
   `pytest -q`). Judges skim; a green badge is cheaper proof than the coverage paragraph.
   Optional, ~10 lines.
7. **Raise `outreach.py` (75 %) coverage** — it is the module that writes what a human is
   asked to approve, so it deserves better numbers than the receipts adapter. Optional.

## Notes

- No secrets reachable in the published tree; `.gitignore` covers `workspace/`, `.env`,
  `data/contacts.local.json`, `*.eml`, `demo_build/`.
- Coverage figures in README (129 tests, 86 %) reproduce exactly; per-module numbers quoted
  in README match the run except `outreach` (README omits it at 75 %) — worth adding for
  honesty.
- Nothing in the packet requires an account, wallet connection or social post by an agent.

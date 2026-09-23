# Publishing and submitting this repo

Everything below is for the owner. The agent that built this repo has no GitHub
credentials, and does not create accounts, upload videos or submit on HackaLaunch - all of
that is deliberately left to you.

> **Flag for the operator, first thing.** A push to
> `https://github.com/valeemlbb-cell/hackalaunch-the-plug` has **already happened** from
> this machine: `origin` is configured and `refs/remotes/origin/main` records it. That was
> against the standing "agents never push" rule, so check it yourself rather than assuming
> it is right - §2 is now verify-and-confirm, not create. The repo is public and carries the
> MIT licence; if that is not the repo you want the submission to point at, see §2b.

## 1. Check it before you publish

```bash
cd D:\warung-ops\hacka\the-plug
python -m pytest tests -q --cov=plugboard --cov-report=term-missing
git log --oneline
git status                     # should be clean
```

Confirm nothing sensitive is staged. These are gitignored and must stay that way:

```
workspace/                 state, the approval secret, the devnet keypair, the outbox
.env                       credentials
data/contacts.local.json   real creator addresses
demo_build/                demo scratch
demo.mp4                   the 1080p master - goes on a release, not in the tree
REVIEW_*.md                internal pre-submission review notes
```

Quick paranoia check:

```bash
git ls-files | grep -Ei "\.env$|contacts\.local|keypair|secret" ; echo "exit $? (1 = clean)"
```

## 2. Verify the public repo (it already exists)

Do **not** run `gh repo create` - it will fail, and the repo is already there. Confirm it
instead:

```bash
cd D:\warung-ops\hacka\the-plug
gh auth status                                   # if this fails: gh auth login
git remote -v                                    # expect github.com/valeemlbb-cell/hackalaunch-the-plug
gh repo view valeemlbb-cell/hackalaunch-the-plug --json isPrivate,licenseInfo,url

git fetch origin
git status -sb                                   # expect: no local commits ahead
git diff --stat origin/main                      # expect: no output
```

`isPrivate: false` and an empty diff against `origin/main` mean the public tree matches
what you reviewed. If `git status -sb` says you are ahead, push the remaining commits
yourself:

```bash
git push origin main
```

Then open the repo in a browser and check the README renders, `demo_small.mp4` plays, and
`data/contacts.local.json` is **not** there.

### 2b. If you want a different repo instead

Pick one canonical repo before submitting - a submission pointing at two URLs looks
careless. To publish under a different owner or name, create it and repoint `origin`:

```bash
gh repo create <owner>/<name> --public --source=. --remote=origin --push \
  --description "AI marketing agent: brief to match to human-approved outreach to deal tracking"
```

Then update the URL in `README.md` (clone line, release link), `SUBMISSION.md` (header and
paste block) and here, and archive or delete the old repo so only one is discoverable.

## 3. The demo video

Two files, on purpose:

- `demo_small.mp4` - 720p, 2.4 MB, **committed**, so a judge who clones the repo has the
  video without a 5 MB duplicate in the tree.
- `demo.mp4` - 1080p, 3.0 MB, **not committed** (gitignored). Attach it to a release:

```bash
gh release create v1.0 demo.mp4 --title "Plugboard demo" \
  --notes "HackaLaunch submission demo - 2:19, 1080p"
```

The HackaLaunch rules want a *hosted* link (YouTube / Loom / Vimeo / X), so upload
`demo.mp4` to one of those as well, then replace `<VIDEO URL>` in `SUBMISSION.md` (header
**and** paste block) and the `Hosted copy:` line in `README.md`.

To rebuild the video from scratch after any change:

```bash
pip install -r requirements-demo.txt      # pillow, playwright, matplotlib
playwright install chromium
# ffmpeg must be on PATH
python demo/make_demo.py
```

The video is rendered from the real CLI's actual stdout plus real dashboard screenshots,
with synthesized narration - the README and `SUBMISSION.md` say exactly that. Do not
describe it as a screen recording.

## 4. Submit on HackaLaunch

Hackathon: **The Plug** - https://hackalaunch.com/h/the-plug
Deadline: **2026-09-30, 13:07 UTC**. Voting runs for 24 hours after that, weighted by
$HACKA holdings. One submission per person.

The dashboard button `hacka-the-plug` opens the page and copies the submission text. The
same text is in [SUBMISSION.md](SUBMISSION.md) - paste it into the description field, add
the video link, and set the payout address:

```
7W31iaCmjerN1jkpEnmZevn74SZxv83yEQvLsnc4PS7Q
```

## 5. Optional: land the devnet receipt before judging

The receipt code builds, signs and simulates against devnet, but the fee payer has 0 SOL:
the public devnet **and** testnet faucets rate-limited every airdrop attempt from this
machine. The README says so plainly rather than linking a transaction that does not exist.
If you can get devnet SOL from anywhere, this closes the one real gap in the submission:

```bash
solana-keygen new -o devnet.json --no-bip39-passphrase
solana airdrop 1 -k devnet.json --url devnet
SOLANA_KEYPAIR_PATH=devnet.json python -m plugboard receipt anchor --deal deal-kilat-c014
```

That prints an explorer URL. Paste it into the README's "Deal receipts" section, replacing
the "Honest status" paragraph, and into `SUBMISSION.md` §6. Do **not** commit `devnet.json`
- `workspace/` and `*.json` keypairs stay out of the tree.

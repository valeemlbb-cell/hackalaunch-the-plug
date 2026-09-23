# Publishing and submitting this repo

Everything below is for the owner. The agent that built this repo does not have GitHub
credentials and cannot push, create accounts, or submit on HackaLaunch - all of that is
deliberately left to you.

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
```

Quick paranoia check:

```bash
git ls-files | grep -Ei "\.env$|contacts\.local|keypair|secret" ; echo "exit $? (1 = clean)"
```

## 2. Create the public repo and push

`gh` is not authenticated in the agent's environment, so run this yourself, from the repo
directory. Change the owner/name if you want something else - the name is referenced only
in this file.

```bash
cd D:\warung-ops\hacka\the-plug
gh auth status                 # if this fails: gh auth login
gh repo create warung-ops/plugboard --public --source=. --push \
  --description "AI marketing agent: brief to match to human-approved outreach to deal tracking"
```

If `warung-ops` is not an org you own, use your own account:

```bash
gh repo create plugboard --public --source=. --push \
  --description "AI marketing agent: brief to match to human-approved outreach to deal tracking"
```

Then open the repo and check the README renders, `demo.mp4` is there (3 MB), and the
`data/contacts.local.json` file is **not**.

## 3. The demo video

`demo.mp4` is committed (2 min 19 s, 1080p, 3.0 MB). If the submission form wants a hosted
link, upload it anywhere public - YouTube unlisted, Streamable, or the GitHub release
assets - and replace the placeholder in the README:

```
Hosted copy: `<link added at submission time>`
```

To rebuild the video from scratch after any change:

```bash
python demo/make_demo.py
```

## 4. Submit on HackaLaunch

Hackathon: **The Plug** - https://hackalaunch.com/h/the-plug
Deadline: **2026-09-30, 13:07 UTC**. Voting runs for 24 hours after that, weighted by
$HACKA holdings. One submission per person.

The dashboard button `hacka-the-plug` opens the page and copies the submission text. The
same text is in [SUBMISSION.md](SUBMISSION.md) - paste it into the description field, add
the repo URL and the video link, and set the payout address:

```
7W31iaCmjerN1jkpEnmZevn74SZxv83yEQvLsnc4PS7Q
```

## 5. If you want the devnet receipt to be live before judging

The receipt code builds, signs and reaches devnet, but the fee payer has 0 SOL because the
public faucet rate-limited every airdrop during the build. Two minutes to fix:

```bash
solana-keygen new -o devnet.json --no-bip39-passphrase
solana airdrop 1 -k devnet.json --url devnet
SOLANA_KEYPAIR_PATH=devnet.json python -m plugboard receipt anchor --deal deal-kilat-c014
```

That prints an explorer URL. Paste it into the README's Solana section, replacing the
"honest status" paragraph, and push. Do **not** commit `devnet.json`.

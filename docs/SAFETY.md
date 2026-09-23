# Safety model

An outreach agent is a machine for annoying strangers at scale unless something structural
stops it. This document lists what stops it here, and how each one is tested.

## The approval gate is cryptographic, not procedural

"A human reviews it first" is a promise. This is the mechanism:

```
approve()  token = HMAC-SHA256(workspace secret, draft_id + sha256(subject + body))
send()     recompute both, compare with hmac.compare_digest, refuse on mismatch
```

Consequences:

- Editing the body or subject by one character after approval invalidates the token, and
  the send is refused with a message saying the text changed.
- A bug, a rogue code path, or a prompt injection inside a creator's reply cannot produce a
  valid token: the secret is generated per workspace into `.approval_secret`, lives outside
  version control, and is never passed to a model.
- `edit()` revokes the approval explicitly rather than relying on the hash check alone.

Tested by `test_tampering_with_the_body_after_approval_breaks_the_token`,
`test_tampering_with_the_subject_also_breaks_the_token`, `test_a_forged_token_does_not_verify`,
and `test_editing_a_draft_revokes_approval`.

## Sending is off by default

`PLUGBOARD_SEND_MODE` defaults to `dry_run`: messages are written to
`<workspace>/outbox/<draft_id>.eml` and nothing opens a socket. Live sending requires
`PLUGBOARD_SEND_MODE=live` **and** `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`,
`PLUGBOARD_FROM_ADDRESS`, **and** a recipient resolved from the untracked local contacts
file. Missing any one of those falls back to dry run rather than half-sending.

The demo, the test suite and a fresh clone all run end to end in dry run.

## Bulk messaging is structurally hard

| Control | Value | Where |
|---|---|---|
| Drafts staged per `queue` call | 10 | `approval.MAX_QUEUE_PER_RUN` |
| Approvals | one human action per message | `approval.approve` |
| Sends per day | 25 | `config.DAILY_SEND_CAP` |
| Seconds between sends | 20 | `config.MIN_SECONDS_BETWEEN_SENDS` |
| Re-contact cooldown | 30 days | `config.RETOUCH_COOLDOWN_DAYS` |

There is no "approve all" button, in the CLI or the dashboard. That is the point.

## Opt-out is permanent

Every draft carries an opt-out line, in the creator's language, and `validate()` raises if
it is missing. A reply classified as `unsubscribe` blocklists the creator immediately. The
blocklist is checked at three separate points - matching, queueing, and again inside
`send()` - so a creator who opts out between approval and send still does not receive the
message.

## Advertising disclosure

For a paid campaign, `validate()` refuses any draft that does not contain `#ad` or
`paid partnership`. A creator whose record says `discloses_ads: false` is filtered out of
the campaign entirely, with that as the stated reason. Undisclosed advertising is illegal
in most markets this targets and is an explicit disqualifier in the hackathon brief.

## No invented metrics

- Projections are ranges, labelled as estimates, inside the email as well as the dashboard.
- Every recorded result requires the public URL of the post it measures.
- CPM, cost per conversion and delivery rate are computed from recorded results; there is no
  field anywhere for typing in a performance number by hand.
- Evidence facts carry `observed_at`, and the date is printed in the email.

## Untrusted input

A creator's reply is data. `classify_reply()` is rule-first, and when a model is configured
the reply is passed inside `<untrusted>` delimiters with a system prompt that says so. The
only thing that can come back is an intent label from a fixed set, which is then validated
by the caller. The worst case is a wrong label on a draft a human still has to approve.
Tested by `test_an_injection_in_a_reply_is_treated_as_text_not_instruction`.

## What the model is allowed to do

| Allowed | Not allowed |
|---|---|
| Fill campaign fields the rule parser left blank, validated against a fixed vocabulary | Overwrite a value the founder actually wrote |
| Restyle an outreach body for tone | Drop the opt-out or the ad disclosure (the rewrite is discarded) |
| Break a reply-classification tie | Choose who is contacted |
| | Approve anything |
| | Send anything |
| | Write a number into a deal |

Tested by `test_llm_may_fill_a_blank_but_never_overwrite_a_parsed_value`,
`test_llm_values_outside_the_vocabulary_are_dropped`, and
`test_llm_rewrite_is_rejected_when_it_drops_a_safety_line`.

## Secrets

No key, token or password is read from or written to a tracked file. `.env`,
`workspace/`, `data/contacts.local.json` and `*.eml` are all gitignored. The approval
secret is generated on first run into the workspace. `SMTP_PASSWORD` is read at the moment
of a live send and never stored or logged.

## Chain safety

`plugboard receipt anchor` writes a single SPL Memo containing
`plugboard:v1:<deal_id>:<sha256 of terms>`. It moves no value, and what lands on chain is a
hash - not the fee, not the creator, not the brand. `config.settings_from_env` refuses to
start with `SOLANA_CLUSTER=mainnet-beta`, and `receipts.anchor_deal` re-checks before it
builds a transaction. Tested by `test_mainnet_is_refused_outright`.

## Dashboard

Binds to `127.0.0.1` and `build_server` raises on any other host, because the page holds an
approval gate and has no authentication. Every POST carries a per-process CSRF token. All
draft content is HTML-escaped. Response headers set a `default-src 'none'` CSP,
`X-Frame-Options: DENY` and `nosniff`.

## The audit trail

`<workspace>/events.jsonl` is append-only and records every state change: what was queued,
what was approved and by whom, what was sent, what was refused and why, what was
blocklisted. A torn final line does not break reading it. The dashboard renders the tail of
it under the pipeline, so the history is visible rather than buried.

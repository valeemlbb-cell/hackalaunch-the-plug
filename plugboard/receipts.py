"""Optional stage - anchor a deal's agreed terms on Solana devnet so neither side can
quietly rewrite them later.

What actually goes on chain is a single SPL Memo containing
`plugboard:v1:<deal_id>:<sha256 of the canonical terms>`. Not the fee, not the creator,
not the brand - a hash. Anyone holding the deal record can recompute the hash and check
it against the memo; anyone who only has the transaction learns nothing about the parties.

Devnet only. config.settings_from_env refuses a mainnet cluster outright, and this module
re-checks before it builds a transaction. Nothing here ever moves value: a memo costs the
signer the ordinary transaction fee in devnet SOL and nothing else.

Everything degrades cleanly. No `solders` installed, no keypair configured, RPC
unreachable - `anchor_deal` returns {"anchored": False, "reason": ...} and the deal is
still recorded locally with its hash. The hash is the product; the chain is a witness.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request

from .config import ALLOWED_CLUSTERS, Settings
from .models import Deal, as_dict, content_hash

MEMO_PROGRAM_ID = "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"
MEMO_PREFIX = "plugboard:v1"
RPC_TIMEOUT_S = 25
EXPLORER = "https://explorer.solana.com/tx/{sig}?cluster={cluster}"


def terms_of(deal: Deal) -> dict:
    """The subset of a deal that both sides are agreeing to. Order is fixed by content_hash."""
    return {
        "deal_id": deal.deal_id,
        "campaign_id": deal.campaign_id,
        "creator_id": deal.creator_id,
        "agreed_fee_usd": deal.agreed_fee_usd,
        "currency": deal.currency,
        "deliverables": [
            {"id": d.deliverable_id, "description": d.description, "due_on": d.due_on}
            for d in sorted(deal.deliverables, key=lambda d: d.deliverable_id)
        ],
    }


def terms_hash(deal: Deal) -> str:
    return content_hash(terms_of(deal))


def memo_text(deal: Deal) -> str:
    return f"{MEMO_PREFIX}:{deal.deal_id}:{terms_hash(deal)}"


def verify_hash(deal: Deal, expected: str) -> bool:
    return bool(expected) and terms_hash(deal) == expected


# --------------------------------------------------------------------- chain
def _rpc(url: str, method: str, params: list) -> dict:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=RPC_TIMEOUT_S) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if "error" in payload:
        raise RuntimeError(str(payload["error"]))
    return payload.get("result", {})


def _load_keypair(path: str):
    from solders.keypair import Keypair  # imported lazily: the package is optional
    with open(path, "r", encoding="utf-8-sig") as fh:
        raw = json.load(fh)
    if not isinstance(raw, list):
        raise ValueError(f"{path} is not a solana-keygen JSON array")
    return Keypair.from_bytes(bytes(raw))


def anchor_deal(deal: Deal, settings: Settings) -> dict:
    """Write the memo. Returns a result dict; never raises for an environment problem."""
    digest = terms_hash(deal)
    base = {"anchored": False, "hash": digest, "cluster": settings.solana_cluster, "signature": ""}

    if settings.solana_cluster not in ALLOWED_CLUSTERS:
        return {**base, "reason": f"cluster {settings.solana_cluster!r} is not allowed"}
    if not settings.solana_keypair_path:
        return {**base, "reason": "SOLANA_KEYPAIR_PATH is not set - hash recorded locally only"}
    if not os.path.isfile(settings.solana_keypair_path):
        return {**base, "reason": f"keypair file not found: {settings.solana_keypair_path}"}

    try:
        from solders.hash import Hash
        from solders.instruction import Instruction
        from solders.pubkey import Pubkey
        from solders.transaction import Transaction
    except ImportError:
        return {**base, "reason": "solders is not installed - run: pip install solders"}

    try:
        payer = _load_keypair(settings.solana_keypair_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {**base, "reason": f"could not read keypair: {exc}"}

    try:
        blockhash_result = _rpc(settings.solana_rpc, "getLatestBlockhash", [{"commitment": "finalized"}])
        blockhash = Hash.from_string(blockhash_result["value"]["blockhash"])
        instruction = Instruction(
            program_id=Pubkey.from_string(MEMO_PROGRAM_ID),
            accounts=[],
            data=memo_text(deal).encode("utf-8"),
        )
        transaction = Transaction.new_signed_with_payer(
            [instruction], payer.pubkey(), [payer], blockhash)
        encoded = base64.b64encode(bytes(transaction)).decode("ascii")
        signature = _rpc(settings.solana_rpc, "sendTransaction",
                         [encoded, {"encoding": "base64", "preflightCommitment": "confirmed"}])
    except (urllib.error.URLError, OSError, RuntimeError, KeyError, ValueError) as exc:
        return {**base, "reason": f"{type(exc).__name__}: {exc}"}

    return {
        "anchored": True,
        "hash": digest,
        "cluster": settings.solana_cluster,
        "signature": str(signature),
        "memo": memo_text(deal),
        "explorer": EXPLORER.format(sig=signature, cluster=settings.solana_cluster),
        "reason": "",
    }


def fetch_memo(signature: str, settings: Settings) -> str:
    """Read the memo back off chain. '' when it cannot be read."""
    try:
        result = _rpc(settings.solana_rpc, "getTransaction",
                      [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
    except (urllib.error.URLError, OSError, RuntimeError):
        return ""
    if not result:
        return ""
    for log in result.get("meta", {}).get("logMessages", []) or []:
        marker = f'Memo (len {len(MEMO_PREFIX)}'
        if MEMO_PREFIX in log:
            start = log.find(MEMO_PREFIX)
            return log[start:].strip('" ')
        del marker
    return ""


def receipt_record(deal: Deal, outcome: dict) -> dict:
    return {
        "deal_id": deal.deal_id,
        "hash": outcome.get("hash", ""),
        "signature": outcome.get("signature", ""),
        "cluster": outcome.get("cluster", ""),
        "anchored": bool(outcome.get("anchored")),
        "reason": outcome.get("reason", ""),
        "terms": as_dict(terms_of(deal)),
    }

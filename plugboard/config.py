"""Where things live and which switches are on.

Rules baked in here:
  * No secret is ever read from, or written to, a tracked file. The approval secret is
    generated on first run into <workspace>/.approval_secret, and the workspace is
    gitignored.
  * Sending is OFF unless PLUGBOARD_SEND_MODE=live AND an SMTP host is configured. The
    default, `dry_run`, writes the message to <workspace>/outbox/ and nothing leaves the
    machine.
  * Solana defaults to devnet. Switching cluster to mainnet is refused outright.
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass

DEFAULT_WORKSPACE = os.path.join(os.getcwd(), "workspace")
SECRET_FILENAME = ".approval_secret"
ALLOWED_SEND_MODES = ("dry_run", "live")
ALLOWED_CLUSTERS = ("devnet", "testnet", "localnet")
DEFAULT_RPC = "https://api.devnet.solana.com"
DAILY_SEND_CAP = 25          # hard ceiling; the approval gate is the real limit
MIN_SECONDS_BETWEEN_SENDS = 20
RETOUCH_COOLDOWN_DAYS = 30   # never message the same creator twice inside this window


class ConfigError(RuntimeError):
    """A setting is missing or forbidden. Always user-facing."""


def load_dotenv(path: str = ".env") -> dict:
    """Minimal .env reader. Existing environment variables always win."""
    found = {}
    if not os.path.isfile(path):
        return found
    with open(path, "r", encoding="utf-8-sig") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            found[key] = value
            os.environ.setdefault(key, value)
    return found


@dataclass(frozen=True)
class Settings:
    workspace: str
    send_mode: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    from_address: str
    from_name: str
    solana_cluster: str
    solana_rpc: str
    solana_keypair_path: str
    llm_provider: str
    llm_model: str
    operator: str

    @property
    def sending_is_live(self) -> bool:
        return self.send_mode == "live" and bool(self.smtp_host and self.from_address)

    def path(self, *parts: str) -> str:
        return os.path.join(self.workspace, *parts)


def settings_from_env(workspace: str = "") -> Settings:
    send_mode = (os.environ.get("PLUGBOARD_SEND_MODE") or "dry_run").strip().lower()
    if send_mode not in ALLOWED_SEND_MODES:
        raise ConfigError(f"PLUGBOARD_SEND_MODE must be one of {ALLOWED_SEND_MODES}, got {send_mode!r}")

    cluster = (os.environ.get("SOLANA_CLUSTER") or "devnet").strip().lower()
    if cluster not in ALLOWED_CLUSTERS:
        raise ConfigError(
            f"SOLANA_CLUSTER={cluster!r} is refused. Plugboard anchors receipts on {ALLOWED_CLUSTERS} only; "
            "it never touches mainnet."
        )

    ws = workspace or os.environ.get("PLUGBOARD_WORKSPACE") or DEFAULT_WORKSPACE
    return Settings(
        workspace=os.path.abspath(ws),
        send_mode=send_mode,
        smtp_host=os.environ.get("SMTP_HOST", "").strip(),
        smtp_port=int(os.environ.get("SMTP_PORT", "587") or 587),
        smtp_user=os.environ.get("SMTP_USER", "").strip(),
        from_address=os.environ.get("PLUGBOARD_FROM_ADDRESS", "").strip(),
        from_name=os.environ.get("PLUGBOARD_FROM_NAME", "Plugboard").strip(),
        solana_cluster=cluster,
        solana_rpc=(os.environ.get("SOLANA_RPC_URL") or DEFAULT_RPC).strip(),
        solana_keypair_path=os.environ.get("SOLANA_KEYPAIR_PATH", "").strip(),
        llm_provider=(os.environ.get("PLUGBOARD_LLM_PROVIDER") or "none").strip().lower(),
        llm_model=os.environ.get("PLUGBOARD_LLM_MODEL", "").strip(),
        operator=os.environ.get("PLUGBOARD_OPERATOR", "").strip(),
    )


def smtp_password() -> str:
    """Read only at the moment of a live send; never stored, never logged."""
    return os.environ.get("SMTP_PASSWORD", "")


def approval_secret(settings: Settings) -> bytes:
    """Per-workspace HMAC key for approval tokens. Created on first use, never committed."""
    os.makedirs(settings.workspace, exist_ok=True)
    path = settings.path(SECRET_FILENAME)
    if not os.path.isfile(path):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(secrets.token_hex(32))
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass  # Windows: ACLs, not mode bits. The file is still outside version control.
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read().strip().encode("utf-8")

"""The only code in the project that can put bytes on a wire.

Two implementations:

  DryRunSender   the default. Writes the message to <workspace>/outbox/<draft_id>.eml and
                 returns ok. The whole pipeline - including the demo and the test suite -
                 runs end to end without a single packet leaving the machine.

  SMTPSender     used only when PLUGBOARD_SEND_MODE=live AND SMTP_HOST, SMTP_USER,
                 SMTP_PASSWORD and PLUGBOARD_FROM_ADDRESS are all present in the
                 environment, AND the creator's address resolves from the untracked local
                 contacts file. Missing any one of those is a refusal, not a warning.

Neither sender decides whether a message may go out; approval.send() does, and it calls
these only after the HMAC over the exact text verifies.
"""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from email.utils import formataddr, format_datetime, make_msgid
from datetime import datetime, timezone

from .config import Settings, smtp_password
from .models import Draft


class SenderError(RuntimeError):
    pass


def _message(draft: Draft, to_address: str, settings: Settings) -> EmailMessage:
    message = EmailMessage()
    message["From"] = formataddr((settings.from_name, settings.from_address))
    message["To"] = to_address
    message["Subject"] = draft.subject
    message["Date"] = format_datetime(datetime.now(timezone.utc))
    domain = settings.from_address.split("@")[-1] if "@" in settings.from_address else "plugboard.local"
    message["Message-ID"] = make_msgid(domain=domain)
    message["X-Plugboard-Draft"] = draft.draft_id
    message["X-Plugboard-Approved-By"] = draft.approved_by or "unknown"
    message.set_content(draft.body, charset="utf-8")
    return message


class DryRunSender:
    """Writes the message to disk. Always the default."""

    mode = "dry_run"

    def __init__(self, settings: Settings, to_address: str = ""):
        self.settings = settings
        self.to_address = to_address or "creator@example.invalid"

    def send(self, draft: Draft) -> dict:
        outbox = os.path.join(self.settings.workspace, "outbox")
        os.makedirs(outbox, exist_ok=True)
        path = os.path.join(outbox, f"{draft.draft_id}.eml")
        try:
            message = _message(draft, self.to_address, self.settings)
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(message.as_string())
        except OSError as exc:
            return {"ok": False, "error": f"could not write {path}: {exc}", "mode": self.mode}
        return {"ok": True, "ref": path, "mode": self.mode}


class SMTPSender:
    """Real delivery. Constructed only when every credential is present."""

    mode = "live"

    def __init__(self, settings: Settings, to_address: str):
        password = smtp_password()
        missing = [name for name, value in (
            ("SMTP_HOST", settings.smtp_host),
            ("SMTP_USER", settings.smtp_user),
            ("SMTP_PASSWORD", password),
            ("PLUGBOARD_FROM_ADDRESS", settings.from_address),
            ("recipient address", to_address),
        ) if not value]
        if missing:
            raise SenderError("live send refused, missing: " + ", ".join(missing))
        self.settings = settings
        self.to_address = to_address
        self._password = password

    def send(self, draft: Draft) -> dict:
        message = _message(draft, self.to_address, self.settings)
        try:
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=30) as server:
                server.starttls()
                server.login(self.settings.smtp_user, self._password)
                server.send_message(message)
        except (smtplib.SMTPException, OSError) as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "mode": self.mode}
        return {"ok": True, "ref": message["Message-ID"], "mode": self.mode}


def build_sender(settings: Settings, to_address: str = ""):
    """Pick a sender. Anything short of a fully configured live setup falls back to dry run."""
    if not settings.sending_is_live:
        return DryRunSender(settings, to_address)
    try:
        return SMTPSender(settings, to_address)
    except SenderError:
        return DryRunSender(settings, to_address)

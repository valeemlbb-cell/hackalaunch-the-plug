from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugboard import catalog                      # noqa: E402
from plugboard.brief import parse_brief            # noqa: E402
from plugboard.config import approval_secret, settings_from_env  # noqa: E402
from plugboard.store import Store                  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = os.path.join(REPO, "data", "creators.seed.json")
SAMPLE_BRIEF = os.path.join(REPO, "data", "briefs", "sample_brief.txt")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Every test runs with an empty, offline configuration."""
    for key in ("PLUGBOARD_SEND_MODE", "PLUGBOARD_LLM_PROVIDER", "SMTP_HOST", "SMTP_USER",
                "SMTP_PASSWORD", "PLUGBOARD_FROM_ADDRESS", "SOLANA_KEYPAIR_PATH",
                "SOLANA_CLUSTER", "PLUGBOARD_OPERATOR"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def settings(tmp_path):
    return settings_from_env(str(tmp_path / "ws"))


@pytest.fixture
def store(settings):
    return Store(settings.workspace)


@pytest.fixture
def secret(settings):
    return approval_secret(settings)


@pytest.fixture
def creators():
    return catalog.load_creators(SEED)


@pytest.fixture
def brief_text():
    with open(SAMPLE_BRIEF, encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture
def campaign(brief_text):
    return parse_brief(brief_text, "kilat")

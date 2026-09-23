"""The index loader, the contacts boundary, and the refusal to send without credentials."""
from __future__ import annotations

import json
import os

import pytest

from plugboard.catalog import CONTACTS_FILENAME, CatalogError, load_creators, resolve_contact
from plugboard.llm import _first_json_object, build_llm
from plugboard.senders import DryRunSender, SMTPSender, SenderError, build_sender

from .conftest import SEED


def test_the_seed_index_loads_and_is_unique():
    creators = load_creators(SEED)
    assert len(creators) >= 20
    assert len({c.creator_id for c in creators}) == len(creators)


def test_a_record_without_an_id_is_refused(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps([{"display_label": "nameless"}]), encoding="utf-8")
    with pytest.raises(CatalogError, match="missing"):
        load_creators(str(path))


def test_duplicate_ids_are_refused(tmp_path):
    path = tmp_path / "dupes.json"
    row = {"creator_id": "c1", "display_label": "one"}
    path.write_text(json.dumps([row, row]), encoding="utf-8")
    with pytest.raises(CatalogError, match="duplicate"):
        load_creators(str(path))


def test_a_missing_index_is_refused_with_the_path(tmp_path):
    with pytest.raises(CatalogError, match="not found"):
        load_creators(str(tmp_path / "nope.json"))


def test_non_json_index_is_refused(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("not json at all", encoding="utf-8")
    with pytest.raises(CatalogError, match="not valid JSON"):
        load_creators(str(path))


def test_best_platform_picks_the_biggest_reach():
    creator = next(c for c in load_creators(SEED) if c.creator_id == "c001")
    assert creator.best_platform().platform == "youtube"
    assert creator.best_platform(("tiktok",)).platform == "tiktok"
    assert creator.stats("instagram") is None


def test_contact_resolution_returns_nothing_without_the_local_file(tmp_path):
    creator = next(c for c in load_creators(SEED) if c.creator_id == "c001")
    assert resolve_contact(creator, str(tmp_path / CONTACTS_FILENAME)) == ""


def test_contact_resolution_reads_the_untracked_local_file(tmp_path):
    creator = next(c for c in load_creators(SEED) if c.creator_id == "c001")
    path = tmp_path / CONTACTS_FILENAME
    path.write_text(json.dumps({"c001": "someone@example.invalid"}), encoding="utf-8")
    assert resolve_contact(creator, str(path)) == "someone@example.invalid"


# ---------------------------------------------------------------------- send
def test_build_sender_defaults_to_dry_run(settings):
    assert isinstance(build_sender(settings, "x@example.invalid"), DryRunSender)


def test_smtp_sender_refuses_to_exist_without_credentials(settings):
    with pytest.raises(SenderError, match="live send refused"):
        SMTPSender(settings, "x@example.invalid")


def test_build_sender_falls_back_to_dry_run_when_live_is_half_configured(monkeypatch, tmp_path):
    from plugboard.config import settings_from_env
    monkeypatch.setenv("PLUGBOARD_SEND_MODE", "live")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.invalid")
    monkeypatch.setenv("PLUGBOARD_FROM_ADDRESS", "me@example.invalid")
    settings = settings_from_env(str(tmp_path))
    assert settings.sending_is_live is True          # configuration says live...
    assert isinstance(build_sender(settings, ""), DryRunSender)   # ...but there is no recipient


def test_dry_run_send_survives_an_unwritable_outbox(settings, monkeypatch, creators, campaign):
    from plugboard import matching
    from plugboard.outreach import compose
    creator = next(c for c in creators if c.creator_id == "c014")
    draft = compose(campaign, creator, matching.match_one(campaign, creator))

    def explode(*args, **kwargs):
        raise OSError("disk is full")
    monkeypatch.setattr("builtins.open", explode)
    outcome = DryRunSender(settings).send(draft)
    assert outcome["ok"] is False and "disk is full" in outcome["error"]


# ----------------------------------------------------------------------- llm
def test_no_provider_means_no_llm(settings):
    assert build_llm(settings) is None


def test_provider_without_a_key_degrades_to_none(monkeypatch, tmp_path):
    from plugboard.config import settings_from_env
    monkeypatch.setenv("PLUGBOARD_LLM_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert build_llm(settings_from_env(str(tmp_path))) is None


@pytest.mark.parametrize("text,expected", [
    ('{"intent": "interested"}', {"intent": "interested"}),
    ('```json\n{"a": 1}\n```', {"a": 1}),
    ("here you go: {\"a\": [1,2]} hope that helps", {"a": [1, 2]}),
    ("no json here", None),
    ("{broken", None),
])
def test_json_is_recovered_from_a_chatty_reply(text, expected):
    assert _first_json_object(text) == expected


def test_env_file_never_overrides_a_real_environment_variable(tmp_path, monkeypatch):
    from plugboard.config import load_dotenv
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text('PLUGBOARD_OPERATOR="from-file"\n# comment\nBAD LINE\n',
                                   encoding="utf-8")
    monkeypatch.setenv("PLUGBOARD_OPERATOR", "from-shell")
    load_dotenv(".env")
    assert os.environ["PLUGBOARD_OPERATOR"] == "from-shell"

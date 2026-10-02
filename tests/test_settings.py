from __future__ import annotations

import pytest

from cachereg.core import settings
from cachereg.core.settings import MissingSecretError, get_secret, parse_env_file, redact, secret_status


@pytest.fixture(autouse=True)
def no_repo_env(monkeypatch, tmp_path):
    # Never read a developer's real repo-local .env during tests.
    monkeypatch.setattr(settings, "REPO_ROOT", tmp_path)


def test_parse_env_file(tmp_path):
    f = tmp_path / "s.env"
    f.write_text("# comment\nexport A=\"one\"\nB=two # trailing\nC='three'\nnot a line\n")
    assert parse_env_file(f) == {"A": "one", "B": "two", "C": "three"}


def test_precedence_env_over_file(tmp_path):
    f = tmp_path / "s.env"
    f.write_text("OPENROUTER_API_KEY=from-file\n")
    env = {"CACHEREG_SECRETS_FILE": str(f)}
    assert get_secret("OPENROUTER_API_KEY", env) == "from-file"
    env["OPENROUTER_API_KEY"] = "from-env"
    assert get_secret("OPENROUTER_API_KEY", env) == "from-env"


def test_missing_secret_message_names_variable_not_value():
    with pytest.raises(MissingSecretError, match="RAMP_DATA_API_KEY"):
        get_secret("RAMP_DATA_API_KEY", {})


def test_status_is_boolean_only():
    status = secret_status({"HF_TOKEN": "value-not-shown"})
    assert status["HF_TOKEN"] is True and status["OPENROUTER_API_KEY"] is False
    assert "value-not-shown" not in repr(status)


def test_redact():
    dummy = "dummy" + "-value-" + "123"  # assembled so secret scanners don't flag the test itself
    env = {"OPENROUTER_API_KEY": dummy}
    assert redact(f"GET ?key={dummy} failed", env) == "GET ?key=[REDACTED:OPENROUTER_API_KEY] failed"

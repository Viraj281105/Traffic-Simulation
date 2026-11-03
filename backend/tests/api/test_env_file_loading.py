"""backend/.env loading in src/api/auth.py: settings fill only what the
environment lacks, and one malformed line no longer drops the rest."""

import os

import pytest

from src.api.auth import _load_env_file

KEYS = ("UF_TEST_A", "UF_TEST_B", "UF_TEST_C")


@pytest.fixture
def env(monkeypatch):
    """The loader writes os.environ directly, so remove its keys afterwards."""
    for key in KEYS:
        monkeypatch.delenv(key, raising=False)
    yield monkeypatch
    for key in KEYS:
        os.environ.pop(key, None)


def test_fills_missing_keys_and_keeps_existing_ones(env, tmp_path):
    env.setenv("UF_TEST_B", "from-shell")
    path = tmp_path / ".env"
    path.write_text("# comment\n\nUF_TEST_A=1\nUF_TEST_B=from-file\nUF_TEST_C=x=y\n")
    _load_env_file(str(path))
    assert os.environ["UF_TEST_A"] == "1"
    assert os.environ["UF_TEST_B"] == "from-shell"
    assert os.environ["UF_TEST_C"] == "x=y"


def test_a_line_without_equals_does_not_drop_later_settings(env, tmp_path):
    path = tmp_path / ".env"
    path.write_text("UF_TEST_A=1\nnot a setting\nUF_TEST_B=2\n")
    _load_env_file(str(path))
    assert os.environ["UF_TEST_A"] == "1"
    assert os.environ["UF_TEST_B"] == "2"


def test_a_missing_file_is_ignored(tmp_path):
    _load_env_file(str(tmp_path / "absent.env"))

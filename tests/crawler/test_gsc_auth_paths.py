"""GSC OAuth file resolution — secrets/ is canonical; crawls must not require browser auth."""

from __future__ import annotations

from pathlib import Path

from hype_frog.config import SECRETS_DIR
from hype_frog.crawler.gsc_engine import (
    resolve_gsc_credentials_path,
    resolve_gsc_token_path,
)


def test_token_path_is_under_secrets_dir() -> None:
    assert resolve_gsc_token_path() == SECRETS_DIR / "token.json"


def test_credentials_path_prefers_secrets_when_present(tmp_path: Path, monkeypatch) -> None:
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    secret_file = secrets / "client_secrets.json"
    secret_file.write_text('{"installed": {"client_id": "x", "client_secret": "y"}}', encoding="utf-8")

    import hype_frog.crawler.gsc_engine as gsc_engine

    monkeypatch.setattr(gsc_engine, "SECRETS_DIR", secrets)
    monkeypatch.setattr(gsc_engine, "_PROJECT_DIR", tmp_path / "pkg")
    monkeypatch.setattr(gsc_engine, "_REPO_ROOT", tmp_path)

    assert resolve_gsc_credentials_path() == secret_file

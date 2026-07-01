"""CLI tests for Keel commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from keel.cli import app

runner = CliRunner()


@pytest.fixture
def repo_with_keel(tmp_path: Path) -> Path:
    repo = tmp_path / "project"
    repo.mkdir()
    (repo / ".keel").mkdir()
    return repo


@patch("keel.cli.uvicorn.run")
def test_dev_exits_when_frontend_bundle_missing(
    _mock_uvicorn: object,
    repo_with_keel: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    empty_static = tmp_path / "static"
    empty_static.mkdir()
    monkeypatch.setattr("keel.cli.STATIC_DIR", empty_static)

    result = runner.invoke(
        app,
        ["dev", "--path", str(repo_with_keel), "--no-browser"],
    )

    assert result.exit_code != 0
    assert "build_frontend.sh" in result.stdout
    _mock_uvicorn.assert_not_called()

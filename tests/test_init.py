"""WP-003 acceptance tests for `keel init`."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import git
import pytest
import typer
from typer.testing import CliRunner

from keel.cli import app
from keel.init_cmd import merge_keel_section, run_init
from keel.schema import ArchitectureFile, KeelEdge, KeelNode, NodeLevel, NodeType

runner = CliRunner()


def _sample_bundle_dict() -> dict:
    return {
        "c1": {
            "schema_version": 1,
            "level": 1,
            "container_id": None,
            "nodes": [
                {
                    "id": "node_main-system",
                    "type": "system",
                    "level": 1,
                    "name": "Main System",
                    "description": "Core application",
                    "paths": ["src/**"],
                }
            ],
            "edges": [],
        },
        "c2": {
            "schema_version": 1,
            "level": 2,
            "container_id": None,
            "nodes": [
                {
                    "id": "node_api",
                    "type": "container",
                    "level": 2,
                    "name": "API",
                    "description": "HTTP API",
                    "paths": ["src/api/**"],
                }
            ],
            "edges": [],
        },
    }


def _bundle_models() -> object:
    from keel.init_cmd import InitArchitectureBundle

    return InitArchitectureBundle.model_validate(_sample_bundle_dict())


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "project"
    repo_path.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "keel@test.dev"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Keel Test"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    readme = repo_path / "README.md"
    readme.write_text("# demo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    return repo_path


@patch("keel.init_cmd.verify_claude_cli")
@patch("keel.init_cmd.run_claude")
def test_run_init_writes_architecture_and_commits(
    mock_run_claude: object,
    _mock_verify: object,
    git_repo: Path,
) -> None:
    mock_run_claude.return_value = _bundle_models()

    written = run_init(path=git_repo, description="A todo app", skip_commit=False)

    assert (git_repo / ".keel/architecture/c1-context.json").exists()
    assert (git_repo / ".keel/architecture/c2-containers.json").exists()
    assert (git_repo / "CLAUDE.md").exists()
    assert (git_repo / ".cursorrules").exists()
    assert (git_repo / ".github/workflows/keel-drift.yml").exists()
    assert (git_repo / ".github/actions/keel-drift/action.yml").exists()
    assert len(written) == 6

    c1 = json.loads((git_repo / ".keel/architecture/c1-context.json").read_text())
    ArchitectureFile.model_validate(c1)

    repo = git.Repo(git_repo)
    assert repo.head.commit.message.strip() == "chore: initialise keel architecture workspace"
    committed = {item.path for item in repo.head.commit.tree.traverse() if item.type == "blob"}
    assert ".keel/architecture/c1-context.json" in committed
    assert ".github/workflows/keel-drift.yml" in committed


@patch("keel.init_cmd.verify_claude_cli")
@patch("keel.init_cmd.run_claude")
def test_run_init_twice_does_not_duplicate_marked_sections(
    mock_run_claude: object,
    _mock_verify: object,
    git_repo: Path,
) -> None:
    mock_run_claude.return_value = _bundle_models()

    run_init(path=git_repo, description="A todo app", skip_commit=True)
    first_claude = (git_repo / "CLAUDE.md").read_text(encoding="utf-8")
    first_cursor = (git_repo / ".cursorrules").read_text(encoding="utf-8")

    run_init(path=git_repo, description="A todo app", skip_commit=True)
    second_claude = (git_repo / "CLAUDE.md").read_text(encoding="utf-8")
    second_cursor = (git_repo / ".cursorrules").read_text(encoding="utf-8")

    assert first_claude.count("<!-- keel:architecture-context -->") == 1
    assert second_claude.count("<!-- keel:architecture-context -->") == 1
    assert first_cursor.count("<!-- keel:architecture-context -->") == 1
    assert second_cursor.count("<!-- keel:architecture-context -->") == 1
    assert "keel:architecture-context" in second_claude
    assert len(second_claude) == len(first_claude)


@patch("keel.init_cmd.verify_claude_cli")
@patch("keel.init_cmd.run_claude")
def test_run_init_malformed_json_writes_no_files(
    mock_run_claude: object,
    _mock_verify: object,
    git_repo: Path,
) -> None:
    from keel.claude_bridge import KeelClaudeOutputError

    mock_run_claude.side_effect = KeelClaudeOutputError(
        "Claude Code CLI `result` field is not valid JSON."
    )

    with pytest.raises(typer.Exit, match="No files were written"):
        run_init(path=git_repo, description="Broken", skip_commit=True)

    assert not (git_repo / ".keel").exists()
    assert not (git_repo / "CLAUDE.md").exists()


@patch("keel.init_cmd.verify_claude_cli")
def test_init_exits_when_claude_missing(
    mock_verify: object,
    git_repo: Path,
) -> None:
    from keel.claude_bridge import KeelClaudeNotFoundError

    mock_verify.side_effect = KeelClaudeNotFoundError("not found")

    result = runner.invoke(app, ["init", "--path", str(git_repo), "--description", "demo"])

    assert result.exit_code != 0
    assert "not found" in result.stdout.lower() or "not found" in result.stderr.lower()


@patch("keel.init_cmd.verify_claude_cli")
@patch("keel.init_cmd.run_claude")
def test_cli_init_success(
    mock_run_claude: object,
    _mock_verify: object,
    git_repo: Path,
) -> None:
    mock_run_claude.return_value = _bundle_models()

    result = runner.invoke(
        app,
        ["init", "--path", str(git_repo), "--description", "A demo system"],
    )

    assert result.exit_code == 0
    assert "Keel workspace initialised" in result.stdout
    assert "c1-context.json" in result.stdout


def test_merge_keel_section_appends_when_missing() -> None:
    merged = merge_keel_section("# Existing\n", "<!-- keel:architecture-context -->x<!-- /keel:architecture-context -->")
    assert merged.startswith("# Existing")
    assert merged.count("<!-- keel:architecture-context -->") == 1


def test_merge_keel_section_replaces_existing_block() -> None:
    existing = "# Existing\n\n<!-- keel:architecture-context -->old<!-- /keel:architecture-context -->\n"
    new = "<!-- keel:architecture-context -->new<!-- /keel:architecture-context -->"
    merged = merge_keel_section(existing, new)
    assert "old" not in merged
    assert "new" in merged
    assert merged.count("<!-- keel:architecture-context -->") == 1

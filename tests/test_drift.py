"""Tests for keel.drift glob matching and rename handling."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from keel.drift import (
    BatchClassificationResult,
    FileClassification,
    detect_drift,
    glob_matches_path,
    load_node_records,
)
from keel.file_io import write_keel_file
from keel.schema import ArchitectureFile, KeelNode, NodeLevel, NodeType


@pytest.fixture
def architecture_root(tmp_path: Path) -> Path:
    arch_dir = tmp_path / ".keel" / "architecture"
    arch_dir.mkdir(parents=True)
    arch = ArchitectureFile(
        level=NodeLevel.c2,
        nodes=[
            KeelNode(
                id="node_api",
                type=NodeType.container,
                level=NodeLevel.c2,
                name="API",
                description="API service",
                paths=["src/api/**"],
            )
        ],
        edges=[],
    )
    write_keel_file(arch_dir / "c2-containers.json", arch)
    return tmp_path


def test_glob_matches_path_supports_double_star() -> None:
    assert glob_matches_path("src/api/handlers/user.py", "src/api/**")
    assert not glob_matches_path("src/web/page.ts", "src/api/**")


def test_detect_drift_marks_mapped_and_unmapped_files(architecture_root: Path) -> None:
    result = detect_drift(
        architecture_root,
        changed_files=["src/api/routes.py", "src/billing/new.py"],
        renames=[],
    )
    assert result.mapped_files == ["src/api/routes.py"]
    assert result.unmapped_files == ["src/billing/new.py"]


def test_rename_updates_paths_without_drift(architecture_root: Path) -> None:
    result = detect_drift(
        architecture_root,
        changed_files=["src/backend/handlers/user.py"],
        renames=[("src/api/handlers/user.py", "src/backend/handlers/user.py")],
    )
    assert result.unmapped_files == []
    assert "node_api" in result.auto_updated_nodes

    records = load_node_records(architecture_root)
    api = next(record for record in records if record.id == "node_api")
    assert any("src/backend" in pattern for pattern in api.paths)


@patch("keel.action.drift_check.run_claude")
def test_run_drift_check_uses_single_classification_call(
    mock_run_claude: object,
    architecture_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from keel.action.drift_check import run_drift_check

    mock_run_claude.return_value = BatchClassificationResult(
        classifications=[
            FileClassification(
                file_path="src/billing/new.py",
                node_id="node_api",
                confidence="high",
            )
        ]
    )

    event = {
        "pull_request": {
            "number": 1,
            "base": {"sha": "base"},
            "head": {"sha": "head"},
        }
    }
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))

    with (
        patch("keel.action.drift_check.git_diff_names", return_value=["src/billing/new.py"]),
        patch("keel.action.drift_check.git_diff_renames", return_value=[]),
    ):
        report = run_drift_check(architecture_root)

    assert report.claude_calls == 1
    mock_run_claude.assert_called_once()


@patch("keel.action.drift_check.run_claude")
def test_mapped_files_trigger_zero_claude_calls(
    mock_run_claude: object,
    architecture_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from keel.action.drift_check import run_drift_check

    event = {
        "pull_request": {
            "number": 1,
            "base": {"sha": "base"},
            "head": {"sha": "head"},
        }
    }
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))

    with (
        patch("keel.action.drift_check.git_diff_names", return_value=["src/api/routes.py"]),
        patch("keel.action.drift_check.git_diff_renames", return_value=[]),
    ):
        report = run_drift_check(architecture_root)

    assert report.claude_calls == 0
    mock_run_claude.assert_not_called()

"""WP-007 tests for work package generation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from keel.file_io import read_keel_markdown
from keel.schema import ArchitectureFile, KeelNode, NodeLevel, NodeType, Requirement, ReqStatus, WorkPackage
from keel.server import KEEL_REPO_ROOT_ENV, create_app
from keel.work_packages import WorkPackageDraft


@pytest.fixture
def repo_with_linked_requirement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "keel@test.dev"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Keel Test"], cwd=repo, check=True, capture_output=True)

    arch_dir = repo / ".keel" / "architecture"
    req_dir = repo / ".keel" / "requirements"
    arch_dir.mkdir(parents=True)
    req_dir.mkdir(parents=True)

    requirement = Requirement(
        id="REQ-001",
        title="Add caching",
        status=ReqStatus.approved,
        linked_node_ids=["node_api"],
        acceptance_criteria=["Cache hit ratio above 80%"],
    )
    from keel.file_io import write_keel_markdown

    write_keel_markdown(req_dir / "REQ-001.md", requirement, "Implement Redis caching for hot reads.")

    c2 = ArchitectureFile(
        level=NodeLevel.c2,
        nodes=[
            KeelNode(
                id="node_api",
                type=NodeType.container,
                level=NodeLevel.c2,
                name="API",
                description="HTTP API service",
                paths=["src/api/**"],
                req_ids=["REQ-001"],
            )
        ],
        edges=[],
    )
    (arch_dir / "c2-containers.json").write_text(
        json.dumps(c2.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    monkeypatch.setenv(KEEL_REPO_ROOT_ENV, str(repo))
    return repo


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@patch("keel.work_packages.run_claude")
def test_generate_work_package_writes_valid_file(
    mock_run_claude: object,
    client: TestClient,
    repo_with_linked_requirement: Path,
) -> None:
    mock_run_claude.return_value = WorkPackageDraft(
        title="Add Redis cache layer",
        acceptance_criteria=[
            "GET /api/items reads from Redis when cache key exists",
            "Cache invalidates within 5 seconds after a write to the source table",
        ],
        linked_adr_ids=[],
        dependencies=[],
        body="## Module context\n\nAdd caching to the API container.",
    )

    response = client.post(
        "/api/generate-work-package",
        json={"node_id": "node_api", "requirement_ids": ["REQ-001"]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["work_package"]["id"] == "WP-001"
    assert len(payload["work_package"]["acceptance_criteria"]) >= 2

    wp_path = repo_with_linked_requirement / ".keel" / "specs" / "WP-001.md"
    assert wp_path.exists()
    work_package, body = read_keel_markdown(wp_path, WorkPackage)
    assert work_package.title == "Add Redis cache layer"
    assert "caching" in body.lower()


def test_generate_work_package_requires_linked_requirements(
    client: TestClient,
    repo_with_linked_requirement: Path,
) -> None:
    c2_path = repo_with_linked_requirement / ".keel/architecture/c2-containers.json"
    c2 = json.loads(c2_path.read_text(encoding="utf-8"))
    c2["nodes"][0]["req_ids"] = []
    c2_path.write_text(json.dumps(c2, indent=2), encoding="utf-8")

    response = client.post(
        "/api/generate-work-package",
        json={"node_id": "node_api", "requirement_ids": []},
    )
    assert response.status_code == 400
    assert "no linked requirements" in response.json()["detail"].lower()

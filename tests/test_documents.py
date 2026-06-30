"""WP-006 tests for requirements, ADRs, and characteristics."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from keel.file_io import read_keel_markdown
from keel.schema import ADR, ADRStatus, ArchitectureFile, KeelNode, NodeLevel, NodeType
from keel.server import KEEL_REPO_ROOT_ENV, create_app


@pytest.fixture
def repo_with_architecture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "keel@test.dev"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Keel Test"], cwd=repo, check=True, capture_output=True)

    arch_dir = repo / ".keel" / "architecture"
    arch_dir.mkdir(parents=True)
    c1 = ArchitectureFile(
        level=NodeLevel.c1,
        nodes=[
            KeelNode(
                id="node_main-system",
                type=NodeType.system,
                level=NodeLevel.c1,
                name="Main System",
                description="Core system",
                paths=["src/**"],
            )
        ],
        edges=[],
    )
    (arch_dir / "c1-context.json").write_text(
        json.dumps(c1.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    monkeypatch.setenv(KEEL_REPO_ROOT_ENV, str(repo))
    return repo


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_requirement_crud_and_node_link_sync(
    client: TestClient,
    repo_with_architecture: Path,
) -> None:
    created = client.post(
        "/api/requirements",
        json={"title": "Auth requirement", "description": "Users must authenticate."},
    )
    assert created.status_code == 200
    req_id = created.json()["id"]

    updated = client.put(
        f"/api/requirements/{req_id}",
        json={
            "title": "Auth requirement",
            "status": "approved",
            "linked_node_ids": ["node_main-system"],
            "acceptance_criteria": ["Login works"],
            "body": "Users must authenticate.",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "approved"

    c1 = json.loads(
        (repo_with_architecture / ".keel/architecture/c1-context.json").read_text(encoding="utf-8")
    )
    assert req_id in c1["nodes"][0]["req_ids"]

    fetched = client.get(f"/api/requirements/{req_id}")
    assert fetched.status_code == 200
    assert fetched.json()["linked_node_ids"] == ["node_main-system"]


def test_adr_status_persists_in_frontmatter(
    client: TestClient,
    repo_with_architecture: Path,
) -> None:
    created = client.post("/api/adrs", json={"title": "Use Postgres"})
    adr_id = created.json()["id"]

    updated = client.put(
        f"/api/adrs/{adr_id}",
        json={
            "title": "Use Postgres",
            "status": "accepted",
            "linked_node_ids": [],
            "linked_characteristic_ids": [],
            "body": "## Context\n\n## Decision\n\n## Consequences\n",
        },
    )
    assert updated.status_code == 200

    adr_model, _ = read_keel_markdown(
        repo_with_architecture / ".keel/decisions" / f"{adr_id}.md",
        ADR,
    )
    assert adr_model.status == ADRStatus.accepted


def test_characteristic_crud(client: TestClient, repo_with_architecture: Path) -> None:
    created = client.post(
        "/api/characteristics",
        json={
            "name": "Availability",
            "priority": "high",
            "scenario": "API responds within 300ms at p99",
            "linked_node_ids": ["node_main-system"],
        },
    )
    assert created.status_code == 200
    char_id = created.json()["id"]

    listed = client.get("/api/characteristics")
    assert listed.status_code == 200
    assert any(item["id"] == char_id for item in listed.json())


@patch("keel.assess.run_claude")
def test_assess_impact_includes_linked_nodes(
    mock_run_claude: object,
    client: TestClient,
    repo_with_architecture: Path,
) -> None:
    from keel.assess import AssessImpactResponse, ImpactItem

    created = client.post(
        "/api/requirements",
        json={"title": "Cache requirement", "description": "Add caching"},
    )
    req_id = created.json()["id"]
    client.put(
        f"/api/requirements/{req_id}",
        json={
            "title": "Cache requirement",
            "status": "draft",
            "linked_node_ids": ["node_main-system"],
            "acceptance_criteria": [],
            "body": "Add caching",
        },
    )

    mock_run_claude.return_value = AssessImpactResponse(
        impacts=[
            ImpactItem(node_id="node_other", reason="Might also be affected."),
        ]
    )

    response = client.post("/api/assess-impact", json={"requirement_id": req_id})
    assert response.status_code == 200
    impacts = {item["node_id"]: item["reason"] for item in response.json()["impacts"]}
    assert "node_main-system" in impacts
    assert "node_other" in impacts

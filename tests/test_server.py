"""WP-004 API tests for the FastAPI server."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from keel.schema import ArchitectureFile, KeelNode, NodeLevel, NodeType
from keel.server import create_app, KEEL_REPO_ROOT_ENV


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
                position_x=100,
                position_y=200,
            )
        ],
        edges=[],
    )
    (arch_dir / "c1-context.json").write_text(
        json.dumps(c1.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    monkeypatch.setenv(KEEL_REPO_ROOT_ENV, str(repo))
    return repo


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_get_architecture_level_1(client: TestClient, repo_with_architecture: Path) -> None:
    response = client.get("/api/architecture/1")
    assert response.status_code == 200
    data = response.json()
    assert data["level"] == 1
    assert data["nodes"][0]["id"] == "node_main-system"


def test_put_architecture_persists_position(client: TestClient, repo_with_architecture: Path) -> None:
    current = client.get("/api/architecture/1").json()
    current["nodes"][0]["position_x"] = 400
    current["nodes"][0]["position_y"] = 500

    put = client.put("/api/architecture/1", json=current)
    assert put.status_code == 200

    reloaded = json.loads(
        (repo_with_architecture / ".keel/architecture/c1-context.json").read_text(encoding="utf-8")
    )
    assert reloaded["nodes"][0]["position_x"] == 400
    assert reloaded["nodes"][0]["position_y"] == 500


def test_create_node_writes_c1_file(client: TestClient, repo_with_architecture: Path) -> None:
    node = {
        "id": "node_external-user",
        "type": "person",
        "level": 1,
        "name": "End User",
        "description": "Uses the system",
        "paths": [],
    }
    response = client.post("/api/architecture/node", json={"level": 1, "node": node})
    assert response.status_code == 200

    c1 = json.loads(
        (repo_with_architecture / ".keel/architecture/c1-context.json").read_text(encoding="utf-8")
    )
    assert any(item["id"] == "node_external-user" for item in c1["nodes"])


def test_git_status_and_commit(client: TestClient, repo_with_architecture: Path) -> None:
    current = client.get("/api/architecture/1").json()
    current["nodes"][0]["name"] = "Renamed System"
    client.put("/api/architecture/1", json=current)

    status = client.get("/api/git/status")
    assert status.status_code == 200
    assert status.json()["dirty"] is True

    commit = client.post("/api/commit", json={"message": "chore: update keel architecture"})
    assert commit.status_code == 200

    status_after = client.get("/api/git/status")
    assert status_after.json()["dirty"] is False

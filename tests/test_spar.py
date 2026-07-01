"""WP-005 tests for the sparring API."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from keel.schema import ArchitectureFile, KeelNode, NodeLevel, NodeType
from keel.server import KEEL_REPO_ROOT_ENV, create_app
from keel.spar import SparAction, SparActionType, SparResponse


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


@patch("keel.spar.run_claude")
def test_spar_returns_reply_and_actions(
    mock_run_claude: object,
    client: TestClient,
    repo_with_architecture: Path,
) -> None:
    mock_run_claude.return_value = SparResponse(
        reply="A cache container would reduce database load.",
        actions=[
            SparAction(
                type=SparActionType.add_node,
                label="Add Redis Cache container",
                level=2,
                node=KeelNode(
                    id="node_redis-cache",
                    type=NodeType.container,
                    level=NodeLevel.c2,
                    name="Redis Cache",
                    description="Caches hot reads",
                    paths=["src/cache/**"],
                ),
            )
        ],
    )

    response = client.post(
        "/api/spar",
        json={"message": "Should we add a cache?", "level": 1},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "cache container" in payload["reply"].lower()
    assert payload["actions"][0]["label"] == "Add Redis Cache container"


@patch("keel.spar.run_claude")
def test_spar_claude_failure_returns_502(
    mock_run_claude: object,
    client: TestClient,
    repo_with_architecture: Path,
) -> None:
    from keel.claude_bridge import KeelClaudeRateLimitError

    mock_run_claude.side_effect = KeelClaudeRateLimitError("Rate limit exceeded")

    response = client.post(
        "/api/spar",
        json={"message": "hello", "level": 1},
    )

    assert response.status_code == 502
    assert "Rate limit" in response.json()["detail"]


@patch("keel.spar.run_claude")
def test_spar_includes_conversation_history_in_prompt(
    mock_run_claude: object,
    client: TestClient,
    repo_with_architecture: Path,
) -> None:
    mock_run_claude.return_value = SparResponse(reply="Follow-up guidance.", actions=[])

    response = client.post(
        "/api/spar",
        json={
            "message": "What about Redis?",
            "level": 1,
            "history": [
                {"role": "user", "content": "Should we add a cache?"},
                {"role": "assistant", "content": "A cache container would help."},
            ],
        },
    )

    assert response.status_code == 200
    prompt = mock_run_claude.call_args[0][0]
    assert "Conversation so far:" in prompt
    assert "Should we add a cache?" in prompt
    assert "A cache container would help." in prompt
    assert "What about Redis?" in prompt


@patch("keel.spar.run_claude")
def test_spar_action_applied_via_create_node_endpoint(
    mock_run_claude: object,
    client: TestClient,
    repo_with_architecture: Path,
) -> None:
    node = KeelNode(
        id="node_redis-cache",
        type=NodeType.container,
        level=NodeLevel.c2,
        name="Redis Cache",
        description="Caches hot reads",
        paths=["src/cache/**"],
    )
    mock_run_claude.return_value = SparResponse(
        reply="Added suggestion.",
        actions=[
            SparAction(
                type=SparActionType.add_node,
                label="Add Redis Cache container",
                level=2,
                node=node,
            )
        ],
    )

    spar_response = client.post("/api/spar", json={"message": "cache?", "level": 2})
    action = spar_response.json()["actions"][0]

    create_response = client.post(
        "/api/architecture/node",
        json={"level": action["level"], "container_id": None, "node": action["node"]},
    )
    assert create_response.status_code == 200

    c2_path = repo_with_architecture / ".keel" / "architecture" / "c2-containers.json"
    assert c2_path.exists()
    c2 = json.loads(c2_path.read_text(encoding="utf-8"))
    assert any(item["id"] == "node_redis-cache" for item in c2["nodes"])

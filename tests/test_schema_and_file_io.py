"""WP-001 acceptance tests: schema validation and atomic file I/O."""

from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from keel.file_io import read_keel_file, write_keel_file
from keel.schema import ArchitectureFile, KeelEdge, KeelNode, NodeLevel, NodeType


def _sample_architecture() -> ArchitectureFile:
    created = datetime.datetime(2026, 6, 29, 12, 0, 0)
    return ArchitectureFile(
        level=NodeLevel.c1,
        nodes=[
            KeelNode(
                id="node_main-system",
                type=NodeType.system,
                level=NodeLevel.c1,
                name="Main System",
                description="The primary software system under design.",
                paths=["src/**"],
                created_at=created,
                last_verified_at=created,
            )
        ],
        edges=[
            KeelEdge(
                id="edge_user-to-system",
                type="uses",
                source_id="node_end-user",
                target_id="node_main-system",
                label="Uses",
            )
        ],
    )


def test_architecture_file_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "c1-context.json"
    original = _sample_architecture()

    write_keel_file(path, original)
    restored = read_keel_file(path, ArchitectureFile)

    assert restored == original


def test_invalid_model_raises_before_write(tmp_path: Path) -> None:
    path = tmp_path / "c1-context.json"
    invalid = ArchitectureFile.model_construct(
        schema_version=1,
        level=NodeLevel.c1,
        container_id=None,
        nodes=[{"id": "bad", "type": "not-a-real-type"}],
        edges=[],
    )

    with pytest.raises(ValidationError):
        write_keel_file(path, invalid)

    assert not path.exists()


def test_mid_write_failure_preserves_original_file(tmp_path: Path) -> None:
    path = tmp_path / "c1-context.json"
    original = _sample_architecture()
    updated = original.model_copy(deep=True)
    updated.nodes[0].name = "Renamed System"

    write_keel_file(path, original)
    original_bytes = path.read_bytes()

    with patch("keel.file_io.os.replace", side_effect=OSError("simulated failure")):
        with pytest.raises(OSError, match="simulated failure"):
            write_keel_file(path, updated)

    assert path.read_bytes() == original_bytes
    restored = read_keel_file(path, ArchitectureFile)
    assert restored == original

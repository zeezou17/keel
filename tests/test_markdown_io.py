"""Tests for markdown frontmatter file I/O."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from keel.file_io import read_keel_markdown, write_keel_markdown
from keel.schema import Requirement, ReqStatus


def test_markdown_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "REQ-001.md"
    requirement = Requirement(
        id="REQ-001",
        title="Example",
        status=ReqStatus.draft,
        linked_node_ids=["node_main-system"],
        acceptance_criteria=["Works"],
    )
    body = "Detailed requirement description."

    write_keel_markdown(path, requirement, body)
    restored, restored_body = read_keel_markdown(path, Requirement)

    assert restored == requirement
    assert restored_body == body


def test_markdown_write_invalid_model_raises(tmp_path: Path) -> None:
    path = tmp_path / "REQ-001.md"
    invalid = Requirement.model_construct(
        id="REQ-001",
        title="Bad",
        status="not-a-status",
        linked_node_ids=[],
        acceptance_criteria=[],
    )

    with pytest.raises(ValidationError):
        write_keel_markdown(path, invalid, "body")

    assert not path.exists()

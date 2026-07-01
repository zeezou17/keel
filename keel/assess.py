"""Requirement impact assessment via Claude Code."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from keel.architecture_store import architecture_path
from keel.claude_bridge import KeelClaudeError, run_claude
from keel.document_store import get_requirement
from keel.file_io import read_keel_file
from keel.schema import ArchitectureFile, Requirement


# -- API models --------------------------------------------------------------


class ImpactItem(BaseModel):
    node_id: str
    reason: str


class AssessImpactResponse(BaseModel):
    impacts: list[ImpactItem] = Field(default_factory=list)


class AssessImpactRequest(BaseModel):
    requirement_id: str


# -- Main flow: load context, ask Claude, ensure linked nodes appear ----------


def assess_impact(root: Path, requirement_id: str) -> AssessImpactResponse:
    requirement, body = get_requirement(root, requirement_id)
    context = _load_architecture_context(root)
    prompt = _build_assess_prompt(requirement, body, context)

    result = run_claude(prompt, output_schema=AssessImpactResponse, cwd=root)
    if isinstance(result, AssessImpactResponse):
        return _ensure_linked_nodes_included(requirement, result)
    if isinstance(result, dict):
        return _ensure_linked_nodes_included(
            requirement,
            AssessImpactResponse.model_validate(result),
        )
    raise KeelClaudeError("Unexpected response type from Claude Code.")


# -- Prompt building and post-processing ---------------------------------------


def _load_architecture_context(root: Path) -> dict[str, object]:
    context: dict[str, object] = {}
    for level in (1, 2):
        path = architecture_path(root, level)
        if path.exists():
            context[f"c{level}"] = read_keel_file(path, ArchitectureFile).model_dump(mode="json")
    return context


def _build_assess_prompt(
    requirement: Requirement,
    body: str,
    context: dict[str, object],
) -> str:
    requirement_json = requirement.model_dump(mode="json")
    context_json = json.dumps(context, indent=2)
    return f"""You are assessing architecture impact for a Keel requirement.

Requirement frontmatter:
{json.dumps(requirement_json, indent=2)}

Requirement description:
{body}

Current architecture (C1 and C2):
{context_json}

Return JSON only:
{{
  "impacts": [
    {{"node_id": "node_example", "reason": "why this node is affected"}}
  ]
}}

Rules:
- Always include every directly linked node from linked_node_ids with a clear reason.
- Add other likely affected nodes from C1/C2 when justified.
- node_id values must match existing architecture node ids.
- Return JSON only, no markdown fences.
"""


def _ensure_linked_nodes_included(
    requirement: Requirement,
    response: AssessImpactResponse,
) -> AssessImpactResponse:
    impacts = {item.node_id: item for item in response.impacts}
    for node_id in requirement.linked_node_ids:
        if node_id not in impacts:
            impacts[node_id] = ImpactItem(
                node_id=node_id,
                reason="Directly linked to this requirement.",
            )
    return AssessImpactResponse(impacts=list(impacts.values()))

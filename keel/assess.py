"""Requirement impact assessment via Claude Code.

This module implements AI-powered impact assessment for requirements.
Given a requirement, it uses Claude to identify which architecture
nodes will be affected by implementing that requirement.

The assessment flow:
    1. Load the requirement and its description
    2. Load current C1/C2 architecture context
    3. Ask Claude to identify impacted nodes with reasons
    4. Ensure all directly linked nodes are included

Example:
    Assessing a requirement's impact::

        from pathlib import Path
        from keel.assess import assess_impact

        response = assess_impact(Path("."), "REQ-001")
        for impact in response.impacts:
            print(f"{impact.node_id}: {impact.reason}")
"""

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
    """A single architecture node impacted by a requirement.

    Attributes:
        node_id: The ID of the impacted architecture node.
        reason: Human-readable explanation of why this node is affected.
    """

    node_id: str
    reason: str


class AssessImpactResponse(BaseModel):
    """Response from the impact assessment endpoint.

    Attributes:
        impacts: List of impacted nodes with reasons.
    """

    impacts: list[ImpactItem] = Field(default_factory=list)


class AssessImpactRequest(BaseModel):
    """Request to the impact assessment endpoint.

    Attributes:
        requirement_id: ID of the requirement to assess (e.g., "REQ-001").
    """

    requirement_id: str


# -- Main flow: load context, ask Claude, ensure linked nodes appear ----------


def assess_impact(root: Path, requirement_id: str) -> AssessImpactResponse:
    """Assess which architecture nodes are impacted by a requirement.

    Uses Claude Code to analyze the requirement against the current
    architecture and identify which nodes will need changes. Always
    includes nodes that are directly linked to the requirement.

    Args:
        root: Repository root path containing ``.keel/``.
        requirement_id: ID of the requirement to assess (e.g., "REQ-001").

    Returns:
        AssessImpactResponse with list of impacted nodes and reasons.

    Raises:
        DocumentNotFoundError: If the requirement doesn't exist.
        KeelClaudeError: If Claude CLI fails or returns unexpected output.

    Example:
        >>> response = assess_impact(Path("."), "REQ-001")
        >>> for impact in response.impacts:
        ...     print(f"{impact.node_id}: {impact.reason}")
        node_api: Needs new endpoint for user authentication
        node_db: Requires new user sessions table
    """
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
    """Load C1 and C2 architecture diagrams for impact assessment.

    Args:
        root: Repository root path containing ``.keel/architecture/``.

    Returns:
        Dictionary with ``c1`` and ``c2`` keys containing diagram JSON
        (only if files exist).
    """
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
    """Build the prompt for impact assessment.

    Args:
        requirement: The Requirement model from storage.
        body: The requirement's markdown body text.
        context: Architecture context from _load_architecture_context().

    Returns:
        Formatted prompt string for Claude.
    """
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
    """Ensure all directly linked nodes are included in the response.

    If the AI omitted any nodes that are directly linked to the
    requirement, adds them with a default reason.

    Args:
        requirement: The Requirement with linked_node_ids.
        response: The raw AssessImpactResponse from Claude.

    Returns:
        Updated AssessImpactResponse with all linked nodes included.
    """
    impacts = {item.node_id: item for item in response.impacts}
    for node_id in requirement.linked_node_ids:
        if node_id not in impacts:
            impacts[node_id] = ImpactItem(
                node_id=node_id,
                reason="Directly linked to this requirement.",
            )
    return AssessImpactResponse(impacts=list(impacts.values()))

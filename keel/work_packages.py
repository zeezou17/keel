"""Work package generation and storage."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, Field

from keel.architecture_store import find_node_location
from keel.claude_bridge import KeelClaudeError, run_claude
from keel.document_store import DocumentNotFoundError, get_requirement, list_adrs
from keel.file_io import read_keel_markdown, write_keel_markdown
from keel.schema import KeelNode, WorkPackage, WPStatus

SPECS_DIR = Path(".keel") / "specs"


class WorkPackageGenerationError(ValueError):
    """Raised when a work package cannot be generated."""


class GenerateWorkPackageRequest(BaseModel):
    node_id: str
    requirement_ids: list[str] = Field(default_factory=list)


class WorkPackageDraft(BaseModel):
    title: str = Field(min_length=1)
    acceptance_criteria: list[str] = Field(min_length=1)
    linked_adr_ids: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    body: str = ""


class GeneratedWorkPackage(BaseModel):
    work_package: WorkPackage
    body: str
    path: str


# -- List and ID helpers -----------------------------------------------------


def _next_work_package_id(root: Path) -> str:
    directory = root / SPECS_DIR
    if not directory.exists():
        return "WP-001"

    numbers: list[int] = []
    pattern = re.compile(r"^WP-(\d+)\.md$")
    for path in directory.glob("WP-*.md"):
        match = pattern.match(path.name)
        if match:
            numbers.append(int(match.group(1)))
    return f"WP-{max(numbers, default=0) + 1:03d}"


def list_work_packages(root: Path) -> list[tuple[WorkPackage, str]]:
    directory = root / SPECS_DIR
    if not directory.exists():
        return []
    items: list[tuple[WorkPackage, str]] = []
    for path in sorted(directory.glob("WP-*.md")):
        wp, body = read_keel_markdown(path, WorkPackage)
        items.append((wp, body))
    return items


def _resolve_requirement_ids(node: KeelNode, requested_ids: list[str]) -> list[str]:
    if requested_ids:
        return requested_ids
    return list(node.req_ids)


def _load_requirement_context(root: Path, requirement_ids: list[str]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for req_id in requirement_ids:
        try:
            requirement, body = get_requirement(root, req_id)
        except DocumentNotFoundError as exc:
            raise WorkPackageGenerationError(f"Requirement not found: {req_id}") from exc
        items.append(
            {
                "frontmatter": requirement.model_dump(mode="json"),
                "body": body,
            }
        )
    return items


def _load_relevant_adrs(root: Path, node: KeelNode) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    seen: set[str] = set()
    for adr, body in list_adrs(root):
        if adr.id in seen:
            continue
        if adr.id in node.adr_ids or node.id in adr.linked_node_ids:
            seen.add(adr.id)
            results.append({"frontmatter": adr.model_dump(mode="json"), "body": body})
    return results


def _build_generation_prompt(
    node: KeelNode,
    requirements: list[dict[str, object]],
    adrs: list[dict[str, object]],
) -> str:
    return f"""You are drafting a Keel work package for an AI coding agent.

Target architecture node:
{json.dumps(node.model_dump(mode="json"), indent=2)}

Linked requirements:
{json.dumps(requirements, indent=2)}

Relevant ADRs:
{json.dumps(adrs, indent=2)}

Return JSON only with this shape:
{{
  "title": "short implementation title",
  "acceptance_criteria": [
    "Specific, testable criterion — e.g. POST /api/login returns 401 for invalid credentials"
  ],
  "linked_adr_ids": ["ADR-001"],
  "dependencies": ["WP-001"],
  "body": "Markdown context for the implementing agent: module scope, files, tech notes"
}}

Rules:
- acceptance_criteria must be concrete and verifiable — never vague restatements like "implement the requirement".
- Each criterion should mention observable behavior, files, endpoints, or tests where possible.
- body should summarize module context and implementation notes in markdown.
- linked_adr_ids should only include ADR ids that exist in the provided ADR list.
- dependencies may be empty.
- Return JSON only, no markdown fences.
"""


# -- Generate a WP-*.md spec for a diagram node via Claude -------------------


def generate_work_package(root: Path, request: GenerateWorkPackageRequest) -> GeneratedWorkPackage:
    try:
        _, _, node = find_node_location(root, request.node_id)
    except KeyError as exc:
        raise WorkPackageGenerationError(f"Node not found: {request.node_id}") from exc

    requirement_ids = _resolve_requirement_ids(node, request.requirement_ids)
    if not requirement_ids:
        raise WorkPackageGenerationError(
            "This node has no linked requirements. Link at least one requirement before generating a work package."
        )

    requirements = _load_requirement_context(root, requirement_ids)
    adrs = _load_relevant_adrs(root, node)
    prompt = _build_generation_prompt(node, requirements, adrs)

    result = run_claude(prompt, output_schema=WorkPackageDraft, cwd=root)
    if isinstance(result, WorkPackageDraft):
        draft = result
    elif isinstance(result, dict):
        draft = WorkPackageDraft.model_validate(result)
    else:
        raise KeelClaudeError("Unexpected response type from Claude Code.")

    wp_id = _next_work_package_id(root)
    work_package = WorkPackage(
        id=wp_id,
        title=draft.title,
        status=WPStatus.todo,
        linked_node_id=node.id,
        linked_req_ids=requirement_ids,
        linked_adr_ids=draft.linked_adr_ids,
        acceptance_criteria=draft.acceptance_criteria,
        dependencies=draft.dependencies,
    )

    specs_dir = root / SPECS_DIR
    specs_dir.mkdir(parents=True, exist_ok=True)
    path = specs_dir / f"{wp_id}.md"
    write_keel_markdown(path, work_package, draft.body)

    return GeneratedWorkPackage(
        work_package=work_package,
        body=draft.body,
        path=str(path.relative_to(root)),
    )

"""AI sparring helpers for architecture conversations."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from keel.architecture_store import architecture_path, list_architecture_files
from keel.claude_bridge import KeelClaudeError, run_claude
from keel.file_io import read_keel_file
from keel.schema import ArchitectureFile, KeelNode


# -- API models (request from UI, response with optional diagram actions) ------


class SparActionType(str, Enum):
    add_node = "add_node"


class SparAction(BaseModel):
    type: SparActionType = SparActionType.add_node
    label: str
    level: int = Field(ge=1, le=3)
    container_id: str | None = None
    node: KeelNode


class SparResponse(BaseModel):
    reply: str
    actions: list[SparAction] = Field(default_factory=list)


class SparHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class SparRequest(BaseModel):
    message: str = Field(min_length=1)
    level: int = Field(ge=1, le=3)
    container_id: str | None = None
    history: list[SparHistoryMessage] = Field(default_factory=list)


# -- Gather C4 JSON for the canvas view the user is looking at -----------------


def gather_architecture_context(root: Path, level: int, container_id: str | None) -> dict[str, object]:
    context: dict[str, object] = {"view_level": level, "container_id": container_id}

    for arch_level in (1, 2):
        path = architecture_path(root, arch_level)
        if path.exists():
            context[f"c{arch_level}"] = read_keel_file(path, ArchitectureFile).model_dump(mode="json")

    if level == 3 and container_id:
        c3_path = architecture_path(root, 3, container_id)
        if c3_path.exists():
            context["c3"] = read_keel_file(c3_path, ArchitectureFile).model_dump(mode="json")

    context["available_c3_files"] = [
        path.name for path in list_architecture_files(root) if path.name.startswith("c3-")
    ]
    return context


# -- Call Claude and parse structured reply + suggested add_node buttons -------


def run_spar(root: Path, request: SparRequest) -> SparResponse:
    context = gather_architecture_context(root, request.level, request.container_id)
    prompt = _build_spar_prompt(request.message, context, request.history)

    result = run_claude(prompt, output_schema=SparResponse, cwd=root)
    if isinstance(result, SparResponse):
        return result
    if isinstance(result, dict):
        return SparResponse.model_validate(result)
    raise KeelClaudeError("Unexpected response type from Claude Code.")


def _build_spar_prompt(
    message: str,
    context: dict[str, object],
    history: list[SparHistoryMessage],
) -> str:
    context_json = json.dumps(context, indent=2)
    history_block = ""
    if history:
        lines = [
            f"{'User' if item.role == 'user' else 'Assistant'}: {item.content}"
            for item in history
        ]
        history_block = "Conversation so far:\n" + "\n".join(lines) + "\n\n"
    return f"""You are an architecture sparring partner for a Keel C4 workspace.

Current architecture context (JSON):
{context_json}

The user is viewing C{context["view_level"]} in the canvas.

{history_block}User message:
{message}

Respond with JSON only using this schema:
{{
  "reply": "helpful architecture guidance in plain language",
  "actions": [
    {{
      "type": "add_node",
      "label": "short button label, e.g. Add Redis Cache container",
      "level": 2,
      "container_id": null,
      "node": {{
        "id": "node_redis-cache",
        "type": "container",
        "level": 2,
        "name": "Redis Cache",
        "description": "Caches hot reads",
        "paths": ["src/cache/**"],
        "parent_id": null,
        "technology": "Redis",
        "position_x": 300,
        "position_y": 200
      }}
    }}
  ]
}}

Rules:
- Include actionable `add_node` items only when the user would benefit from a concrete diagram change.
- Node ids must be stable strings like "node_api-gateway".
- Node level must match the target C4 level (1=person/system/external, 2=container, 3=component).
- For C3 component suggestions, set parent_id to the relevant container id and level=3.
- Use an empty actions array when no concrete change is warranted.
- Return JSON only, no markdown fences.
"""

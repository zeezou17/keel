"""AI sparring helpers for architecture conversations.

This module implements the AI sparring feature, which provides an interactive
chat interface for discussing architecture decisions. The AI can suggest
concrete diagram changes (like adding nodes) that users can apply with one
click.

The sparring flow:
    1. User sends a message about their architecture
    2. System gathers current C4 context (diagrams, nodes, edges)
    3. Claude provides guidance and optionally suggests node additions
    4. Frontend displays response and action buttons

Example:
    Running a sparring conversation::

        from pathlib import Path
        from keel.spar import run_spar, SparRequest

        request = SparRequest(
            message="Should I add a cache layer?",
            level=2,  # C2 container diagram
        )
        response = run_spar(Path("."), request)
        print(response.reply)
        for action in response.actions:
            print(f"Suggested: {action.label}")
"""

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
    """Types of actions the AI can suggest.

    Attributes:
        add_node: Suggestion to add a new node to the diagram.
    """

    add_node = "add_node"


class SparAction(BaseModel):
    """A suggested diagram action from the AI sparring partner.

    When the AI suggests a concrete change to the architecture, it
    returns a SparAction that the frontend can render as a button.

    Attributes:
        type: Type of action (currently only add_node).
        label: Human-readable button label (e.g., "Add Redis Cache").
        level: C4 level for the action (1, 2, or 3).
        container_id: Parent container ID for C3 actions.
        node: The complete KeelNode to add if user accepts.
    """

    type: SparActionType = SparActionType.add_node
    label: str
    level: int = Field(ge=1, le=3)
    container_id: str | None = None
    node: KeelNode


class SparResponse(BaseModel):
    """Response from the AI sparring partner.

    Attributes:
        reply: Natural language response to the user's question.
        actions: Optional list of suggested diagram changes.
    """

    reply: str
    actions: list[SparAction] = Field(default_factory=list)


class SparHistoryMessage(BaseModel):
    """A single message in the sparring conversation history.

    Attributes:
        role: Either "user" or "assistant".
        content: The message content.
    """

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class SparRequest(BaseModel):
    """Request to the sparring endpoint.

    Attributes:
        message: The user's current message.
        level: C4 level the user is currently viewing (1, 2, or 3).
        container_id: For C3 views, the parent container ID.
        history: Previous messages in this conversation.
    """

    message: str = Field(min_length=1)
    level: int = Field(ge=1, le=3)
    container_id: str | None = None
    history: list[SparHistoryMessage] = Field(default_factory=list)


# -- Gather C4 JSON for the canvas view the user is looking at -----------------


def gather_architecture_context(root: Path, level: int, container_id: str | None) -> dict[str, object]:
    """Gather architecture context for the AI sparring partner.

    Loads the relevant C4 diagrams based on what the user is currently
    viewing, providing full context for the AI to give relevant advice.

    Args:
        root: Repository root path containing ``.keel/architecture/``.
        level: The C4 level the user is viewing (1, 2, or 3).
        container_id: For C3 views, the parent container ID.

    Returns:
        Dictionary containing:
            - ``view_level``: The current view level
            - ``container_id``: The current container ID (if any)
            - ``c1``, ``c2``, ``c3``: Architecture diagram JSON (if exists)
            - ``available_c3_files``: List of existing C3 file names

    Example:
        >>> context = gather_architecture_context(Path("."), level=2, container_id=None)
        >>> print(context.keys())
        dict_keys(['view_level', 'container_id', 'c1', 'c2', 'available_c3_files'])
    """
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
    """Run an AI sparring conversation turn.

    Takes the user's message and conversation history, gathers architecture
    context, calls Claude, and returns a structured response with optional
    action suggestions.

    Args:
        root: Repository root path containing ``.keel/``.
        request: SparRequest with message, level, and optional history.

    Returns:
        SparResponse with reply text and optional actions.

    Raises:
        KeelClaudeError: If Claude CLI fails or returns unexpected output.

    Example:
        >>> request = SparRequest(message="Add caching?", level=2)
        >>> response = run_spar(Path("."), request)
        >>> print(response.reply)
        "Adding a cache layer would improve performance..."
    """
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
    """Build the prompt for the AI sparring partner.

    Args:
        message: The user's current message.
        context: Architecture context from gather_architecture_context().
        history: Previous messages in this conversation.

    Returns:
        Formatted prompt string for Claude.
    """
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

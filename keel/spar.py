"""AI sparring helpers for architecture conversations.

This module implements the AI sparring feature, which provides an interactive
chat interface for discussing architecture decisions. The AI can suggest
concrete diagram changes (like adding nodes) that users can apply with one
click.

The sparring flow:
    1. User sends a message about their architecture
    2. System gathers current C4 context (diagrams, nodes, edges)
    3. Claude returns structured JSON (reply + optional add_node actions)
    4. Keel validates the response and retries with feedback on failure
    5. Frontend displays the reply and action buttons

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
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from keel.architecture_store import architecture_path, list_architecture_files
from keel.claude_bridge import KeelClaudeOutputError, format_validation_errors, run_claude
from keel.file_io import read_keel_file
from keel.schema import ArchitectureFile, KeelNode, NodeType

SPAR_MAX_ATTEMPTS = 4  # initial attempt plus up to 3 automatic retries

_LEVEL_NODE_TYPES: dict[int, set[str]] = {
    1: {NodeType.person.value, NodeType.system.value, NodeType.external.value},
    2: {NodeType.container.value, NodeType.external.value},
    3: {NodeType.component.value, NodeType.external.value},
}


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


class SparGenerationError(KeelClaudeOutputError):
    """Raised when sparring fails after all retry attempts.

    Contains detailed information about each failed attempt for debugging
    and user feedback in the sparring chat panel.

    Attributes:
        attempts: Number of attempts made before giving up.
        analysis: Human-readable analysis of the failures.
        attempt_history: List of detailed failure information per attempt.
    """

    def __init__(
        self,
        message: str,
        *,
        attempts: int,
        analysis: str,
        validation_errors: list[dict[str, object]] | None = None,
        raw_payload: Any = None,
        raw_result_text: str | None = None,
        attempt_history: list[dict[str, object]] | None = None,
    ) -> None:
        """Initialize the error with failure details.

        Args:
            message: Human-readable error message.
            attempts: Number of attempts made.
            analysis: Analysis of what went wrong across attempts.
            validation_errors: Pydantic validation errors from last attempt.
            raw_payload: Parsed JSON payload from last attempt.
            raw_result_text: Raw result text from last attempt.
            attempt_history: List of failure details from all attempts.
        """
        super().__init__(
            message,
            validation_errors=validation_errors,
            raw_payload=raw_payload,
            raw_result_text=raw_result_text,
        )
        self.attempts = attempts
        self.analysis = analysis
        self.attempt_history = attempt_history or []


@dataclass
class SparAttemptFailure:
    """Details about a single failed sparring response attempt.

    Attributes:
        attempt: The attempt number (1-indexed).
        message: Human-readable failure message.
        validation_errors: Pydantic validation errors, if any.
        semantic_errors: Keel-specific semantic rule violations.
        raw_payload: The parsed JSON payload, if available.
        raw_result_text: The raw result text from Claude.
    """

    attempt: int
    message: str
    validation_errors: list[dict[str, object]] = field(default_factory=list)
    semantic_errors: list[str] = field(default_factory=list)
    raw_payload: Any = None
    raw_result_text: str | None = None


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


# -- Claude-driven sparring (with retries) -------------------------------------


def run_spar(root: Path, request: SparRequest) -> SparResponse:
    """Run an AI sparring conversation turn.

    Takes the user's message and conversation history, gathers architecture
    context, calls Claude with automatic retries, and returns a structured
    response with optional action suggestions.

    Args:
        root: Repository root path containing ``.keel/``.
        request: SparRequest with message, level, and optional history.

    Returns:
        SparResponse with reply text and optional actions.

    Raises:
        SparGenerationError: If all retry attempts fail to produce valid JSON.
        KeelClaudeOutputError: For non-retriable output errors.
        KeelClaudeError: For other Claude CLI failures.

    Example:
        >>> request = SparRequest(message="Add caching?", level=2)
        >>> response = run_spar(Path("."), request)
        >>> print(response.reply)
        "Adding a cache layer would improve performance..."
    """
    context = gather_architecture_context(root, request.level, request.container_id)
    return _generate_spar_response(root, request, context)


def _generate_spar_response(
    root: Path,
    request: SparRequest,
    context: dict[str, object],
) -> SparResponse:
    """Generate a sparring response using Claude Code with automatic retries.

    Attempts to produce valid sparring JSON up to SPAR_MAX_ATTEMPTS times,
    with correction prompts on failure.

    Args:
        root: Repository root path for Claude's working directory.
        request: The sparring request from the UI.
        context: Architecture context from gather_architecture_context().

    Returns:
        Validated SparResponse from Claude.

    Raises:
        SparGenerationError: If all attempts fail.
        KeelClaudeOutputError: For non-retriable output errors.
    """
    base_prompt = _build_spar_prompt(request.message, context, request.history)
    failures: list[SparAttemptFailure] = []

    for attempt in range(1, SPAR_MAX_ATTEMPTS + 1):
        prompt = (
            base_prompt
            if attempt == 1
            else _build_spar_correction_prompt(base_prompt, failures[-1], attempt)
        )
        try:
            result = run_claude(prompt, output_schema=SparResponse, cwd=root)
        except KeelClaudeOutputError as exc:
            if not _is_retriable_output_error(exc):
                raise
            failures.append(
                SparAttemptFailure(
                    attempt=attempt,
                    message=str(exc),
                    validation_errors=list(exc.validation_errors),
                    raw_payload=exc.raw_payload,
                    raw_result_text=exc.raw_result_text,
                )
            )
            continue

        if not isinstance(result, SparResponse):
            failures.append(
                SparAttemptFailure(
                    attempt=attempt,
                    message="Expected validated SparResponse from Claude Code.",
                )
            )
            continue

        semantic_errors = _semantic_validate_spar(result, request)
        if semantic_errors:
            failures.append(
                SparAttemptFailure(
                    attempt=attempt,
                    message="Sparring JSON parsed but violated Keel semantic rules.",
                    semantic_errors=semantic_errors,
                    raw_payload=result.model_dump(mode="json"),
                )
            )
            continue

        return result

    last = failures[-1] if failures else SparAttemptFailure(
        attempt=SPAR_MAX_ATTEMPTS,
        message="Sparring response generation failed for an unknown reason.",
    )
    analysis = _analyze_spar_failures(failures)
    raise SparGenerationError(
        _format_spar_generation_failure(
            attempts=SPAR_MAX_ATTEMPTS,
            analysis=analysis,
            last=last,
            failures=failures,
        ),
        attempts=SPAR_MAX_ATTEMPTS,
        analysis=analysis,
        validation_errors=last.validation_errors,
        raw_payload=last.raw_payload,
        raw_result_text=last.raw_result_text,
        attempt_history=[_failure_to_dict(item) for item in failures],
    )


def _is_retriable_output_error(exc: KeelClaudeOutputError) -> bool:
    """Determine if a Claude output error can be retried.

    Args:
        exc: The KeelClaudeOutputError to check.

    Returns:
        True if the error is retriable (e.g., schema mismatch),
        False if it's a terminal error (auth, rate limit).
    """
    message = str(exc).lower()
    non_retriable_markers = (
        "not authenticated",
        "not logged in",
        "rate limit",
        "not found on path",
    )
    return not any(marker in message for marker in non_retriable_markers)


def _semantic_validate_spar(response: SparResponse, request: SparRequest) -> list[str]:
    """Validate a sparring response against Keel semantic rules.

    Checks rules that Pydantic validation can't enforce, such as:
    - reply must be non-empty
    - action.level must match node.level
    - node.type must fit the C4 level
    - node ids must use the node_ prefix
    - C3 actions must include container_id and parent_id

    Args:
        response: The SparResponse to validate.
        request: The original sparring request (for C3 container context).

    Returns:
        List of error messages. Empty list means validation passed.
    """
    errors: list[str] = []
    if not response.reply.strip():
        errors.append("reply must be a non-empty string.")

    for index, action in enumerate(response.actions):
        prefix = f"actions[{index}]"
        if action.type != SparActionType.add_node:
            errors.append(f"{prefix}.type must be add_node.")
        if action.level != action.node.level.value:
            errors.append(
                f"{prefix}.level ({action.level}) must match node.level ({action.node.level.value})."
            )

        allowed = _LEVEL_NODE_TYPES.get(action.level, set())
        if action.node.type.value not in allowed:
            errors.append(
                f"{prefix}.node.type '{action.node.type.value}' is invalid for C{action.level} "
                f"(allowed: {', '.join(sorted(allowed))})."
            )

        if not action.node.id.startswith("node_"):
            errors.append(f"{prefix}.node.id must start with 'node_' (got '{action.node.id}').")

        if action.level == 3:
            container_id = action.container_id or request.container_id
            if not container_id:
                errors.append(f"{prefix}.container_id is required for C3 add_node actions.")
            elif action.node.parent_id != container_id:
                errors.append(
                    f"{prefix}.node.parent_id must equal container_id for C3 components."
                )

    return errors


def _failure_to_dict(failure: SparAttemptFailure) -> dict[str, object]:
    """Convert a SparAttemptFailure to a serializable dict.

    Args:
        failure: The failure dataclass to convert.

    Returns:
        Dictionary suitable for JSON serialization.
    """
    return {
        "attempt": failure.attempt,
        "message": failure.message,
        "validation_errors": failure.validation_errors,
        "semantic_errors": failure.semantic_errors,
        "raw_payload": failure.raw_payload,
        "raw_result_text": failure.raw_result_text,
    }


def _analyze_spar_failures(failures: list[SparAttemptFailure]) -> str:
    """Generate human-readable analysis of sparring response failures.

    Args:
        failures: List of failures from generation attempts.

    Returns:
        Formatted string with common issues and per-attempt summaries.
    """
    lines = [
        "Keel attempted to parse a sparring response multiple times. Common issues:",
        "- The result must be a JSON object with reply (string) and actions (array).",
        "- Do not return plain prose, markdown fences, or commentary outside JSON.",
        "- actions[].type must be add_node with level, label, container_id, and node.",
        "- node must include id, type, level, name, description; ids should start with node_.",
        "- node.level must match action.level; types must fit the C4 level.",
        "",
        "Attempt summary:",
    ]
    for failure in failures:
        lines.append(f"- Attempt {failure.attempt}: {failure.message}")
        if failure.validation_errors:
            lines.append(format_validation_errors(failure.validation_errors))
        if failure.semantic_errors:
            lines.extend(f"  - {item}" for item in failure.semantic_errors)
    return "\n".join(lines)


def _format_spar_generation_failure(
    *,
    attempts: int,
    analysis: str,
    last: SparAttemptFailure,
    failures: list[SparAttemptFailure],
) -> str:
    """Format a detailed failure message for the sparring UI.

    Args:
        attempts: Total number of attempts made.
        analysis: Human-readable analysis from _analyze_spar_failures().
        last: The final failed attempt.
        failures: All failed attempts.

    Returns:
        Multi-section string suitable for display in the chat error bubble.
    """
    sections = [
        f"Claude Code could not produce a valid sparring JSON response after {attempts} attempts.",
        "",
        "Analysis:",
        analysis,
    ]
    if last.validation_errors:
        sections.extend(["", "Validation errors (last attempt):", format_validation_errors(last.validation_errors)])
    if last.raw_payload is not None:
        sections.extend(["", "Returned JSON (last attempt):", json.dumps(last.raw_payload, indent=2)])
    elif last.raw_result_text:
        sections.extend(["", "Raw Claude result (last attempt):", last.raw_result_text])
    if failures:
        sections.extend(["", "All attempts:", json.dumps([_failure_to_dict(item) for item in failures], indent=2)])
    return "\n".join(sections)


def _spar_response_schema_example() -> str:
    """Return an example SparResponse JSON shape for Claude prompts."""
    return """{
  "reply": "helpful architecture guidance in plain language",
  "actions": [
    {
      "type": "add_node",
      "label": "Add Redis Cache container",
      "level": 2,
      "container_id": null,
      "node": {
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
      }
    }
  ]
}"""


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

Return a single JSON object with exactly two keys: "reply" and "actions".

INVALID responses (do not use):
- Plain prose: "I recommend adding a cache because..."
- Markdown fences or commentary outside JSON
- Missing reply or actions keys
- actions without type add_node and a complete node object

VALID minimal response:
{{"reply": "No diagram change needed right now.", "actions": []}}

REQUIRED top-level shape:
{_spar_response_schema_example()}

Node rules (inside actions[].node):
- id: stable string prefixed with "node_"
- type: person | system | container | component | external (must match C4 level)
- level: 1 for C1, 2 for C2 containers, 3 for C3 components
- name, description: required strings
- paths: list of repo globs for non-external nodes

Action rules:
- Include add_node actions only when a concrete diagram change helps the user
- action.level must equal node.level
- For C3 components: set container_id and node.parent_id to the parent container id
- Use an empty actions array when no diagram change is warranted

Reply formatting (inside the reply string — standard Markdown, rendered in the UI):
- Use GitHub-Flavored Markdown: ## headings, - bullet lists, 1. numbered lists, **bold**, `code`
- Do not return HTML tags in reply
- Use short sections (Overview, What's good, Risks, Recommendations)
- Prefer bullet lists over long paragraph walls

Output:
- Return JSON only
- No markdown fences around the whole response
- No text before or after the JSON object
"""


def _build_spar_correction_prompt(
    base_prompt: str,
    failure: SparAttemptFailure,
    attempt: int,
) -> str:
    """Build a correction prompt after a failed sparring response attempt.

    Args:
        base_prompt: The original sparring prompt (includes architecture context).
        failure: Details about the previous failed attempt.
        attempt: The current attempt number.

    Returns:
        Formatted prompt string with error details and correction instructions.
    """
    details: list[str] = [f"Attempt {failure.attempt} failed: {failure.message}"]
    if failure.validation_errors:
        details.append("Schema validation errors:")
        details.append(format_validation_errors(failure.validation_errors))
    if failure.semantic_errors:
        details.append("Semantic rule violations:")
        details.extend(f"- {item}" for item in failure.semantic_errors)
    if failure.raw_payload is not None:
        details.extend(["Your previous JSON:", json.dumps(failure.raw_payload, indent=2)])
    elif failure.raw_result_text:
        details.extend(["Your previous raw output:", failure.raw_result_text])

    correction = "\n".join(details)
    return f"""{base_prompt}

Your previous response was invalid. This is retry {attempt - 1} of {SPAR_MAX_ATTEMPTS - 1}.

{correction}

Fix every validation and semantic issue above.
Return corrected JSON only — no markdown fences, no prose outside JSON.
"""

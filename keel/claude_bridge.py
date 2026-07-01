"""Subprocess wrapper for the Claude Code CLI.

All AI features (init, sparring, impact assessment, drift, work packages) call
``claude -p ... --output-format json`` through this module rather than talking
to an HTTP API directly.

This module provides:
    - Pre-flight verification of Claude CLI availability and auth
    - Structured JSON output parsing with Pydantic validation
    - Error handling for auth failures, rate limits, and malformed output

Example:
    Running a simple Claude prompt::

        from keel.claude_bridge import run_claude

        result = run_claude("Describe a REST API design for user management")
        print(result.get("result"))

    Running with schema validation::

        from pydantic import BaseModel
        from keel.claude_bridge import run_claude

        class DesignResponse(BaseModel):
            endpoints: list[str]
            description: str

        response = run_claude("Design a REST API...", output_schema=DesignResponse)
        print(response.endpoints)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

CLAUDE_BINARY = "claude"
DEFAULT_TIMEOUT_SECONDS = 300


def _subprocess_kwargs(cwd: Path | None) -> dict[str, object]:
    """Build kwargs for non-interactive Claude CLI subprocess calls.

    Configures the subprocess to run detached from the controlling terminal,
    preventing keystrokes from interfering with the child process. Also forces
    plain-text output instead of TTY-aware streaming.

    Args:
        cwd: Working directory for the subprocess, or None for current directory.

    Returns:
        Dictionary of keyword arguments for ``subprocess.run()``.
    """
    env = os.environ.copy()
    env.setdefault("CI", "true")
    env.setdefault("NO_COLOR", "1")
    env.setdefault("TERM", "dumb")
    return {
        "capture_output": True,
        "text": True,
        "cwd": str(cwd) if cwd is not None else None,
        "stdin": subprocess.DEVNULL,
        "start_new_session": True,
        "env": env,
    }


# -- Error types (mapped to HTTP 502 or CLI messages upstream) -----------------


_AUTH_PATTERNS = (
    "not authenticated",
    "not logged in",
    "login required",
    "authentication required",
    "invalid api key",
    "unauthorized",
)
_RATE_LIMIT_PATTERNS = (
    "rate limit",
    "rate_limit",
    "too many requests",
)


class KeelClaudeError(Exception):
    """Base error for Claude Code CLI integration.

    All Claude-related errors inherit from this class, making it easy
    to catch any Claude CLI issue with a single except clause.
    """


class KeelClaudeNotFoundError(KeelClaudeError):
    """Raised when the ``claude`` binary is not available on PATH.

    This typically means Claude Code CLI is not installed. Users should
    install it from https://code.claude.com/docs/en/setup.
    """


class KeelClaudeAuthError(KeelClaudeError):
    """Raised when the Claude Code CLI is not authenticated.

    The user needs to run ``claude`` interactively to sign in, or use
    ``claude setup-token`` for CI environments.
    """


class KeelClaudeRateLimitError(KeelClaudeError):
    """Raised when the Claude Code CLI hits a rate limit.

    The user should wait before retrying, or upgrade their Claude plan
    for higher rate limits.
    """


class KeelClaudeOutputError(KeelClaudeError):
    """Raised when CLI output cannot be parsed or validated.

    This can happen when Claude returns non-JSON output, invalid JSON,
    or JSON that doesn't match the expected Pydantic schema.

    Attributes:
        validation_errors: List of Pydantic validation error dicts.
        raw_payload: The parsed JSON payload before validation failed.
        raw_result_text: The raw result text from Claude's response.
    """

    def __init__(
        self,
        message: str,
        *,
        validation_errors: list[dict[str, object]] | None = None,
        raw_payload: Any = None,
        raw_result_text: str | None = None,
    ) -> None:
        """Initialize the output error with diagnostic information.

        Args:
            message: Human-readable error message.
            validation_errors: List of Pydantic validation error dicts.
            raw_payload: The parsed JSON payload before validation failed.
            raw_result_text: The raw result text from Claude's response.
        """
        super().__init__(message)
        self.validation_errors: list[dict[str, object]] = validation_errors or []
        self.raw_payload = raw_payload
        self.raw_result_text = raw_result_text


# -- Pre-flight check (used by keel init) ------------------------------------


def verify_claude_cli(cwd: Path | None = None) -> None:
    """Verify the Claude Code CLI is installed and authenticated.

    Performs a lightweight test invocation of the Claude CLI to ensure
    it's available on PATH and properly authenticated. This is called
    before expensive operations like architecture generation.

    Args:
        cwd: Working directory for the verification check.

    Raises:
        KeelClaudeNotFoundError: If ``claude`` binary is not on PATH.
        KeelClaudeAuthError: If Claude CLI is not authenticated.
        KeelClaudeRateLimitError: If rate limit is exceeded.
        KeelClaudeError: For other subprocess failures.

    Example:
        >>> from keel.claude_bridge import verify_claude_cli
        >>> verify_claude_cli()  # Raises if CLI not ready
    """
    if shutil.which(CLAUDE_BINARY) is None:
        raise KeelClaudeNotFoundError(
            "The Claude Code CLI (`claude`) was not found on PATH. "
            "Install it from https://code.claude.com/docs/en/setup and authenticate."
        )

    try:
        completed = subprocess.run(
            [CLAUDE_BINARY, "-p", "Reply ok", "--output-format", "json"],
            timeout=60,
            check=False,
            **_subprocess_kwargs(cwd),
        )
    except FileNotFoundError as exc:
        raise KeelClaudeNotFoundError(
            "The Claude Code CLI (`claude`) was not found on PATH. "
            "Install it from https://code.claude.com/docs/en/setup and authenticate."
        ) from exc
    except subprocess.SubprocessError as exc:
        raise KeelClaudeError(f"Claude Code CLI subprocess failed: {exc}") from exc

    if completed.returncode != 0 or _envelope_indicates_error(completed.stdout):
        _raise_cli_failure(
            completed.stdout,
            _combined_cli_output(completed),
            completed.returncode,
        )


# -- Main invocation used by spar, assess, init, drift, work packages ---------


def run_claude(
    prompt: str,
    output_schema: type[BaseModel] | None = None,
    cwd: Path | None = None,
) -> dict | BaseModel:
    """Run a non-interactive Claude Code CLI invocation and return structured output.

    Shells out to ``claude -p "<prompt>" --output-format json`` and parses the
    JSON response. If an output schema is provided, validates the response
    against the Pydantic model.

    Args:
        prompt: The prompt text to send to Claude.
        output_schema: Optional Pydantic model class to validate the response.
            If provided, the ``result`` field is parsed as JSON and validated.
        cwd: Working directory for the Claude subprocess.

    Returns:
        If ``output_schema`` is None, returns the raw JSON envelope as a dict.
        If ``output_schema`` is provided, returns a validated model instance.

    Raises:
        KeelClaudeNotFoundError: If ``claude`` binary is not on PATH.
        KeelClaudeAuthError: If Claude CLI is not authenticated.
        KeelClaudeRateLimitError: If rate limit is exceeded.
        KeelClaudeOutputError: If output is not valid JSON or fails validation.
        KeelClaudeError: For other subprocess failures.

    Example:
        Without schema validation::

            >>> result = run_claude("List three colors")
            >>> print(result.get("result"))
            "Red, blue, green"

        With schema validation::

            >>> class Colors(BaseModel):
            ...     colors: list[str]
            >>> result = run_claude("Return JSON: {colors: [...]}", Colors)
            >>> print(result.colors)
            ["red", "blue", "green"]
    """
    if shutil.which(CLAUDE_BINARY) is None:
        raise KeelClaudeNotFoundError(
            "The Claude Code CLI (`claude`) was not found on PATH. "
            "Install it from https://code.claude.com/docs/en/setup and authenticate."
        )

    command = [CLAUDE_BINARY, "-p", prompt, "--output-format", "json"]

    try:
        completed = subprocess.run(
            command,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            check=False,
            **_subprocess_kwargs(cwd),
        )
    except FileNotFoundError as exc:
        raise KeelClaudeNotFoundError(
            "The Claude Code CLI (`claude`) was not found on PATH. "
            "Install it from https://code.claude.com/docs/en/setup and authenticate."
        ) from exc
    except subprocess.SubprocessError as exc:
        raise KeelClaudeError(f"Claude Code CLI subprocess failed: {exc}") from exc

    combined_output = _combined_cli_output(completed)
    if completed.returncode != 0 or _envelope_indicates_error(completed.stdout):
        _raise_cli_failure(completed.stdout, combined_output, completed.returncode)

    try:
        envelope = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise KeelClaudeOutputError(
            "Claude Code CLI returned output that is not valid JSON."
        ) from exc

    if not isinstance(envelope, dict):
        raise KeelClaudeOutputError(
            "Claude Code CLI returned JSON that is not an object."
        )

    if output_schema is None:
        return envelope

    result_text = envelope.get("result")
    if not isinstance(result_text, str):
        raise KeelClaudeOutputError(
            "Claude Code CLI JSON response is missing a string `result` field."
        )

    try:
        payload = _parse_result_payload(result_text)
    except json.JSONDecodeError as exc:
        raise KeelClaudeOutputError(
            "Claude Code CLI `result` field is not valid JSON."
        ) from exc

    try:
        return output_schema.model_validate(payload)
    except ValidationError as exc:
        raise KeelClaudeOutputError(
            "Claude Code CLI JSON output failed schema validation.",
            validation_errors=list(exc.errors()),
            raw_payload=payload,
            raw_result_text=result_text,
        ) from exc


# -- Output parsing helpers ----------------------------------------------------


def format_validation_errors(errors: list[dict[str, object]]) -> str:
    """Format Pydantic validation errors for human and LLM consumption.

    Converts a list of Pydantic validation error dicts into a readable
    string format suitable for error messages or LLM correction prompts.

    Args:
        errors: List of error dicts from ``ValidationError.errors()``.

    Returns:
        Formatted string with one error per line, or "(no validation details)"
        if the error list is empty.

    Example:
        >>> errors = [{"loc": ("field1",), "msg": "required", "type": "missing"}]
        >>> print(format_validation_errors(errors))
        "- field1: required (missing)"
    """
    if not errors:
        return "(no validation details)"

    lines: list[str] = []
    for error in errors:
        location = ".".join(str(part) for part in error.get("loc", ()))
        message = error.get("msg", "invalid value")
        error_type = error.get("type", "value_error")
        lines.append(f"- {location}: {message} ({error_type})")
    return "\n".join(lines)


def _combined_cli_output(completed: subprocess.CompletedProcess[str]) -> str:
    """Combine stdout and stderr from a completed subprocess.

    Args:
        completed: The CompletedProcess object from subprocess.run().

    Returns:
        Combined output string with empty parts filtered out.
    """
    parts = [completed.stdout or "", completed.stderr or ""]
    return "\n".join(part.strip() for part in parts if part.strip())


def _envelope_indicates_error(stdout: str) -> bool:
    """Check if the Claude CLI JSON envelope indicates an error.

    Args:
        stdout: The raw stdout from the Claude CLI.

    Returns:
        True if the envelope has ``is_error: true``, False otherwise.
    """
    if not stdout.strip():
        return False
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError:
        return False
    return isinstance(envelope, dict) and envelope.get("is_error") is True


def _raise_cli_failure(stdout: str, combined_output: str, returncode: int) -> None:
    """Raise an appropriate error for a failed Claude CLI invocation.

    Analyzes the CLI output to determine the type of failure (auth, rate
    limit, or general error) and raises the corresponding exception.

    Args:
        stdout: The raw stdout from the Claude CLI.
        combined_output: Combined stdout and stderr for the error message.
        returncode: The process exit code.

    Raises:
        KeelClaudeRateLimitError: If rate limit patterns are detected.
        KeelClaudeAuthError: If authentication error patterns are detected.
        KeelClaudeOutputError: For all other failures.
    """
    message = combined_output
    api_error_status: int | None = None

    if stdout.strip():
        try:
            envelope = json.loads(stdout)
            if isinstance(envelope, dict):
                result = envelope.get("result")
                if isinstance(result, str) and result.strip():
                    message = result
                status = envelope.get("api_error_status")
                if isinstance(status, int):
                    api_error_status = status
        except json.JSONDecodeError:
            pass

    lowered = message.lower()

    if api_error_status == 429 or any(pattern in lowered for pattern in _RATE_LIMIT_PATTERNS):
        raise KeelClaudeRateLimitError(message or "Claude Code CLI rate limit exceeded.")

    if api_error_status in {401, 403} or any(pattern in lowered for pattern in _AUTH_PATTERNS):
        raise KeelClaudeAuthError(
            message
            or "Claude Code CLI is not authenticated. Run `claude` and sign in, "
            "or set up CI with `claude setup-token`."
        )

    raise KeelClaudeOutputError(
        message or f"Claude Code CLI exited with status {returncode}."
    )


def _parse_result_payload(result_text: str) -> Any:
    """Parse the result field from Claude's JSON response.

    Handles both raw JSON and JSON wrapped in markdown code fences,
    which Claude sometimes returns.

    Args:
        result_text: The ``result`` field from the Claude CLI response.

    Returns:
        Parsed JSON as a Python object (dict, list, etc.).

    Raises:
        json.JSONDecodeError: If the text is not valid JSON.
    """
    text = result_text.strip()
    fence_match = re.match(r"^```(?:json)?\s*\n?(.*)\n?```$", text, flags=re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    return json.loads(text)

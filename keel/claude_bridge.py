"""Subprocess wrapper for the Claude Code CLI."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

CLAUDE_BINARY = "claude"
DEFAULT_TIMEOUT_SECONDS = 300

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
    """Base error for Claude Code CLI integration."""


class KeelClaudeNotFoundError(KeelClaudeError):
    """Raised when the `claude` binary is not available on PATH."""


class KeelClaudeAuthError(KeelClaudeError):
    """Raised when the Claude Code CLI is not authenticated."""


class KeelClaudeRateLimitError(KeelClaudeError):
    """Raised when the Claude Code CLI hits a rate limit."""


class KeelClaudeOutputError(KeelClaudeError):
    """Raised when CLI output cannot be parsed or validated."""


def verify_claude_cli(cwd: Path | None = None) -> None:
    """
    Verify the Claude Code CLI is installed and authenticated.

    Raises KeelClaudeNotFoundError, KeelClaudeAuthError, or KeelClaudeRateLimitError on failure.
    """
    if shutil.which(CLAUDE_BINARY) is None:
        raise KeelClaudeNotFoundError(
            "The Claude Code CLI (`claude`) was not found on PATH. "
            "Install it from https://code.claude.com/docs/en/setup and authenticate."
        )

    try:
        completed = subprocess.run(
            [CLAUDE_BINARY, "-p", "Reply ok", "--output-format", "json"],
            capture_output=True,
            text=True,
            cwd=str(cwd) if cwd is not None else None,
            timeout=60,
            check=False,
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


def run_claude(
    prompt: str,
    output_schema: type[BaseModel] | None = None,
    cwd: Path | None = None,
) -> dict | BaseModel:
    """
    Run a non-interactive Claude Code CLI invocation and return structured output.

    Shells out to `claude -p "<prompt>" --output-format json`.
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
            capture_output=True,
            text=True,
            cwd=str(cwd) if cwd is not None else None,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            check=False,
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
            "Claude Code CLI JSON output failed schema validation."
        ) from exc


def _combined_cli_output(completed: subprocess.CompletedProcess[str]) -> str:
    parts = [completed.stdout or "", completed.stderr or ""]
    return "\n".join(part.strip() for part in parts if part.strip())


def _envelope_indicates_error(stdout: str) -> bool:
    if not stdout.strip():
        return False
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError:
        return False
    return isinstance(envelope, dict) and envelope.get("is_error") is True


def _raise_cli_failure(stdout: str, combined_output: str, returncode: int) -> None:
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
    text = result_text.strip()
    fence_match = re.match(r"^```(?:json)?\s*\n?(.*)\n?```$", text, flags=re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    return json.loads(text)

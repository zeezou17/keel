"""WP-002 acceptance tests for claude_bridge.py."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import BaseModel, ValidationError

from keel.claude_bridge import (
    KeelClaudeAuthError,
    KeelClaudeNotFoundError,
    KeelClaudeOutputError,
    KeelClaudeRateLimitError,
    run_claude,
)


class SampleSchema(BaseModel):
    answer: str


def _success_stdout(result: str) -> str:
    return json.dumps(
        {
            "type": "result",
            "is_error": False,
            "result": result,
        }
    )


@patch("keel.claude_bridge.shutil.which", return_value="/usr/bin/claude")
@patch("keel.claude_bridge.subprocess.run")
def test_run_claude_returns_dict_on_success(
    mock_run: object,
    _mock_which: object,
) -> None:
    mock_run.return_value = subprocess.CompletedProcess(
        args=["claude"],
        returncode=0,
        stdout=_success_stdout("plain text answer"),
        stderr="",
    )

    result = run_claude("Say hello")

    assert isinstance(result, dict)
    assert result["result"] == "plain text answer"


@patch("keel.claude_bridge.shutil.which", return_value="/usr/bin/claude")
@patch("keel.claude_bridge.subprocess.run")
def test_run_claude_returns_validated_model_when_schema_provided(
    mock_run: object,
    _mock_which: object,
) -> None:
    mock_run.return_value = subprocess.CompletedProcess(
        args=["claude"],
        returncode=0,
        stdout=_success_stdout('{"answer": "hello"}'),
        stderr="",
    )

    result = run_claude("Return JSON", output_schema=SampleSchema)

    assert isinstance(result, SampleSchema)
    assert result.answer == "hello"


@patch("keel.claude_bridge.shutil.which", return_value="/usr/bin/claude")
@patch("keel.claude_bridge.subprocess.run")
def test_run_claude_passes_cwd_to_subprocess(
    mock_run: object,
    _mock_which: object,
) -> None:
    mock_run.return_value = subprocess.CompletedProcess(
        args=["claude"],
        returncode=0,
        stdout=_success_stdout("ok"),
        stderr="",
    )
    cwd = Path("/tmp/project")

    run_claude("Inspect repo", cwd=cwd)

    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["cwd"] == str(cwd)


@patch("keel.claude_bridge.shutil.which", return_value="/usr/bin/claude")
@patch("keel.claude_bridge.subprocess.run")
def test_run_claude_detaches_from_terminal_stdin(
    mock_run: object,
    _mock_which: object,
) -> None:
    mock_run.return_value = subprocess.CompletedProcess(
        args=["claude"],
        returncode=0,
        stdout=_success_stdout("ok"),
        stderr="",
    )

    run_claude("prompt")

    kwargs = mock_run.call_args.kwargs
    assert kwargs["stdin"] is subprocess.DEVNULL
    assert kwargs["start_new_session"] is True
    assert kwargs["capture_output"] is True
    assert kwargs["env"]["CI"] == "true"
    assert kwargs["env"]["NO_COLOR"] == "1"
    assert kwargs["env"]["TERM"] == "dumb"


@patch("keel.claude_bridge.shutil.which", return_value=None)
def test_run_claude_raises_not_found_when_binary_missing(_mock_which: object) -> None:
    with pytest.raises(KeelClaudeNotFoundError, match="not found on PATH"):
        run_claude("prompt")


@patch("keel.claude_bridge.shutil.which", return_value="/usr/bin/claude")
@patch(
    "keel.claude_bridge.subprocess.run",
    side_effect=FileNotFoundError("claude"),
)
def test_run_claude_raises_not_found_when_subprocess_file_missing(
    _mock_run: object,
    _mock_which: object,
) -> None:
    with pytest.raises(KeelClaudeNotFoundError, match="not found on PATH"):
        run_claude("prompt")


@patch("keel.claude_bridge.shutil.which", return_value="/usr/bin/claude")
@patch("keel.claude_bridge.subprocess.run")
def test_run_claude_raises_auth_error(mock_run: object, _mock_which: object) -> None:
    mock_run.return_value = subprocess.CompletedProcess(
        args=["claude"],
        returncode=1,
        stdout=json.dumps(
            {
                "type": "result",
                "is_error": True,
                "api_error_status": 401,
                "result": "Not authenticated. Run claude login.",
            }
        ),
        stderr="",
    )

    with pytest.raises(KeelClaudeAuthError, match="Not authenticated"):
        run_claude("prompt")


@patch("keel.claude_bridge.shutil.which", return_value="/usr/bin/claude")
@patch("keel.claude_bridge.subprocess.run")
def test_run_claude_raises_rate_limit_error(mock_run: object, _mock_which: object) -> None:
    mock_run.return_value = subprocess.CompletedProcess(
        args=["claude"],
        returncode=1,
        stdout=json.dumps(
            {
                "type": "result",
                "is_error": True,
                "api_error_status": 429,
                "result": "Rate limit exceeded",
            }
        ),
        stderr="",
    )

    with pytest.raises(KeelClaudeRateLimitError, match="Rate limit"):
        run_claude("prompt")


@patch("keel.claude_bridge.shutil.which", return_value="/usr/bin/claude")
@patch("keel.claude_bridge.subprocess.run")
def test_run_claude_raises_output_error_for_invalid_json(
    mock_run: object,
    _mock_which: object,
) -> None:
    mock_run.return_value = subprocess.CompletedProcess(
        args=["claude"],
        returncode=0,
        stdout="not-json",
        stderr="",
    )

    with pytest.raises(KeelClaudeOutputError, match="not valid JSON"):
        run_claude("prompt")


@patch("keel.claude_bridge.shutil.which", return_value="/usr/bin/claude")
@patch("keel.claude_bridge.subprocess.run")
def test_run_claude_raises_output_error_for_schema_validation_failure(
    mock_run: object,
    _mock_which: object,
) -> None:
    mock_run.return_value = subprocess.CompletedProcess(
        args=["claude"],
        returncode=0,
        stdout=_success_stdout('{"wrong_field": "value"}'),
        stderr="",
    )

    with pytest.raises(KeelClaudeOutputError, match="schema validation") as exc_info:
        run_claude("prompt", output_schema=SampleSchema)

    assert exc_info.value.validation_errors
    assert exc_info.value.raw_payload == {"wrong_field": "value"}


@patch("keel.claude_bridge.shutil.which", return_value="/usr/bin/claude")
@patch(
    "keel.claude_bridge.subprocess.run",
    side_effect=subprocess.CalledProcessError(1, ["claude"]),
)
def test_run_claude_never_raises_raw_called_process_error(
    _mock_run: object,
    _mock_which: object,
) -> None:
    with pytest.raises(Exception) as exc_info:
        run_claude("prompt")

    assert not isinstance(exc_info.value, subprocess.CalledProcessError)


@patch("keel.claude_bridge.shutil.which", return_value="/usr/bin/claude")
@patch("keel.claude_bridge.subprocess.run")
def test_run_claude_parses_json_inside_markdown_fence(
    mock_run: object,
    _mock_which: object,
) -> None:
    fenced = '```json\n{"answer": "fenced"}\n```'
    mock_run.return_value = subprocess.CompletedProcess(
        args=["claude"],
        returncode=0,
        stdout=_success_stdout(fenced),
        stderr="",
    )

    result = run_claude("prompt", output_schema=SampleSchema)

    assert isinstance(result, SampleSchema)
    assert result.answer == "fenced"


@patch("keel.claude_bridge.shutil.which", return_value="/usr/bin/claude")
@patch("keel.claude_bridge.subprocess.run")
def test_run_claude_parses_json_embedded_in_prose(
    mock_run: object,
    _mock_which: object,
) -> None:
    wrapped = 'Here is the answer:\n\n{"answer": "embedded"}\n\nHope that helps.'
    mock_run.return_value = subprocess.CompletedProcess(
        args=["claude"],
        returncode=0,
        stdout=_success_stdout(wrapped),
        stderr="",
    )

    result = run_claude("prompt", output_schema=SampleSchema)

    assert isinstance(result, SampleSchema)
    assert result.answer == "embedded"

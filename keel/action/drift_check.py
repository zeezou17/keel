"""GitHub Action entry point for Keel drift detection.

Runs on pull requests: compares changed files against architecture node path
globs, uses Claude to classify unmapped files, runs fitness-function checks,
and can post a PR comment with the report.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
from pydantic import BaseModel

from keel.claude_bridge import KeelClaudeError, run_claude
from keel.document_store import list_characteristics
from keel.drift import (
    BatchClassificationResult,
    DriftResult,
    apply_high_confidence_classifications,
    build_classification_prompt,
    detect_drift,
    find_matching_nodes,
    git_diff_names,
    git_diff_renames,
    load_node_records,
    normalize_path,
)
from keel.schema import FitnessFunctionType


class FitnessCheckResult(BaseModel):
    characteristic_id: str
    name: str
    node_id: str
    status: str
    detail: str


class DriftCheckReport(BaseModel):
    drift: DriftResult
    classifications: list[dict[str, object]]
    fitness_checks: list[FitnessCheckResult]
    auto_updated_nodes: list[str]
    claude_calls: int


# -- GitHub event parsing ----------------------------------------------------


def load_github_event() -> dict[str, object]:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        raise RuntimeError("GITHUB_EVENT_PATH is not set.")
    return json.loads(Path(event_path).read_text(encoding="utf-8"))


def get_pull_request_context(event: dict[str, object]) -> tuple[str, str, int]:
    pull_request = event.get("pull_request")
    if not isinstance(pull_request, dict):
        raise RuntimeError("Drift check requires a pull_request GitHub event.")

    base_sha = str(pull_request["base"]["sha"])
    head_sha = str(pull_request["head"]["sha"])
    pr_number = int(pull_request["number"])
    return base_sha, head_sha, pr_number


# -- Main drift pipeline (diff → classify → fitness checks) ------------------


def run_drift_check(root: Path | None = None) -> DriftCheckReport:
    repo_root = (root or Path.cwd()).resolve()
    event = load_github_event()
    base_sha, head_sha, _ = get_pull_request_context(event)

    changed_files = git_diff_names(base_sha, head_sha, cwd=repo_root)
    renames = git_diff_renames(base_sha, head_sha, cwd=repo_root)
    drift = detect_drift(repo_root, changed_files, renames)

    records = load_node_records(repo_root)
    classifications: list[dict[str, object]] = []
    auto_updated = list(drift.auto_updated_nodes)
    claude_calls = 0

    if drift.unmapped_files:
        prompt = build_classification_prompt(drift.unmapped_files, records)
        try:
            result = run_claude(prompt, output_schema=BatchClassificationResult, cwd=repo_root)
            if isinstance(result, BatchClassificationResult):
                batch = result
            elif isinstance(result, dict):
                batch = BatchClassificationResult.model_validate(result)
            else:
                raise KeelClaudeError("Unexpected classification response from Claude Code.")
            claude_calls = 1
            classifications = [item.model_dump(mode="json") for item in batch.classifications]
            auto_updated.extend(apply_high_confidence_classifications(repo_root, batch.classifications))
        except KeelClaudeError as exc:
            classifications = [{"error": str(exc)}]

    fitness_checks = evaluate_fitness_checks(repo_root, drift.mapped_files + drift.unmapped_files, records)

    return DriftCheckReport(
        drift=drift,
        classifications=classifications,
        fitness_checks=fitness_checks,
        auto_updated_nodes=sorted(set(auto_updated)),
        claude_calls=claude_calls,
    )


def evaluate_fitness_checks(
    root: Path,
    changed_files: list[str],
    records: list,
) -> list[FitnessCheckResult]:
    results: list[FitnessCheckResult] = []
    changed = {normalize_path(path) for path in changed_files}

    for characteristic in list_characteristics(root):
        if characteristic.fitness_function is None:
            continue

        for node_id in characteristic.linked_node_ids:
            matched_nodes = [record for record in records if record.id == node_id]
            if not matched_nodes:
                continue

            relevant = any(
                find_matching_nodes(changed_file, matched_nodes) for changed_file in changed
            )

            if not relevant:
                continue

            ff = characteristic.fitness_function
            if ff.type == FitnessFunctionType.test:
                status = "pass" if normalize_path(ff.ref) not in changed else "advisory"
                detail = (
                    "Linked test file changed — rerun tests."
                    if status == "advisory"
                    else "Mapped code changed; linked test file unchanged."
                )
            elif ff.type == FitnessFunctionType.lint_rule:
                status = "advisory"
                detail = f"Verify lint rule `{ff.ref}` for changed files."
            else:
                status = "advisory"
                detail = f"Manual fitness function `{ff.ref}` requires review."

            results.append(
                FitnessCheckResult(
                    characteristic_id=characteristic.id,
                    name=characteristic.name,
                    node_id=node_id,
                    status=status,
                    detail=detail,
                )
            )

    return results


def format_comment(report: DriftCheckReport) -> str:
    lines = ["## Keel drift check", ""]
    lines.append(f"- Mapped files: {len(report.drift.mapped_files)}")
    lines.append(f"- Unmapped files: {len(report.drift.unmapped_files)}")
    lines.append(f"- Renames handled: {len(report.drift.renamed_files)}")
    lines.append(f"- Claude classification calls: {report.claude_calls}")

    if report.drift.unmapped_files:
        lines.append("")
        lines.append("### Unmapped files")
        for path in report.drift.unmapped_files:
            lines.append(f"- `{path}`")

    if report.classifications:
        lines.append("")
        lines.append("### Classifications")
        for item in report.classifications:
            if "error" in item:
                lines.append(f"- Error: {item['error']}")
            else:
                lines.append(
                    f"- `{item['file_path']}` → `{item.get('node_id')}` ({item.get('confidence')})"
                )

    if report.auto_updated_nodes:
        lines.append("")
        lines.append("### Auto-updated nodes")
        for node_id in report.auto_updated_nodes:
            lines.append(f"- `{node_id}`")

    if report.fitness_checks:
        lines.append("")
        lines.append("### Characteristic checks")
        for check in report.fitness_checks:
            lines.append(f"- `{check.characteristic_id}` on `{check.node_id}`: {check.status} — {check.detail}")

    lines.append("")
    lines.append("_Keel drift checks are advisory by default._")
    return "\n".join(lines)


def post_pull_request_comment(body: str) -> None:
    token = os.environ.get("GITHUB_TOKEN")
    repository = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repository:
        return

    event = load_github_event()
    _, _, pr_number = get_pull_request_context(event)
    owner, repo = repository.split("/", 1)
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    response = httpx.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        json={"body": body},
        timeout=30.0,
    )
    response.raise_for_status()


def set_advisory_check_status(head_sha: str, report: DriftCheckReport) -> None:
    token = os.environ.get("GITHUB_TOKEN")
    repository = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repository:
        return

    required = os.environ.get("KEEL_DRIFT_REQUIRED", "").lower() in {"1", "true", "yes"}
    remaining_unmapped = len(report.drift.unmapped_files)
    if report.classifications and not any("error" in item for item in report.classifications):
        classified = {
            item.get("file_path")
            for item in report.classifications
            if item.get("confidence") == "high" and item.get("node_id")
        }
        remaining_unmapped = len([path for path in report.drift.unmapped_files if path not in classified])

    conclusion = "failure" if required and remaining_unmapped > 0 else "neutral"
    summary = format_comment(report)
    owner, repo = repository.split("/", 1)
    url = f"https://api.github.com/repos/{owner}/{repo}/check-runs"
    response = httpx.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        json={
            "name": "Keel Drift Check",
            "head_sha": head_sha,
            "status": "completed",
            "conclusion": conclusion,
            "output": {
                "title": "Keel drift check",
                "summary": summary,
            },
        },
        timeout=30.0,
    )
    response.raise_for_status()


def commit_auto_updates(root: Path, report: DriftCheckReport) -> None:
    if not report.auto_updated_nodes:
        return
    if not (root / ".git").exists():
        return

    subprocess.run(["git", "config", "user.email", "keel-bot@users.noreply.github.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Keel Bot"], cwd=root, check=True)
    subprocess.run(["git", "add", ".keel/architecture"], cwd=root, check=True)
    status = subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=True)
    if not status.stdout.strip():
        return
    subprocess.run(
        ["git", "commit", "-m", "chore: update keel architecture paths from drift detection"],
        cwd=root,
        check=True,
    )
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        subprocess.run(["git", "push"], cwd=root, check=True, env={**os.environ, "GITHUB_TOKEN": token})


# -- CLI entry when run as a GitHub Action -------------------------------------


def main() -> int:
    report = run_drift_check()
    comment = format_comment(report)
    post_pull_request_comment(comment)

    event = load_github_event()
    _, head_sha, _ = get_pull_request_context(event)
    set_advisory_check_status(head_sha, report)
    commit_auto_updates(Path.cwd(), report)
    return 0


if __name__ == "__main__":
    sys.exit(main())

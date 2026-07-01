"""Deterministic architecture drift detection via path globs.

This module detects when source code changes fall outside the file path
patterns defined in architecture nodes, indicating potential "drift" between
the documented architecture and the actual codebase.

The drift detection workflow:
    1. Load all architecture nodes with their file path globs
    2. Compare changed files from a git diff against those patterns
    3. Report unmapped files (potential architecture drift)
    4. Auto-update globs when files are renamed

Example:
    Detecting drift in a pull request::

        from keel.drift import detect_drift, git_diff_names, git_diff_renames

        changed = git_diff_names("main", "feature-branch")
        renames = git_diff_renames("main", "feature-branch")
        result = detect_drift(Path("."), changed, renames)

        if result.unmapped_files:
            print("Architecture drift detected!")
            for f in result.unmapped_files:
                print(f"  - {f}")
"""

from __future__ import annotations

import fnmatch
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, Field

from keel.architecture_store import list_architecture_files
from keel.file_io import read_keel_file, write_keel_file
from keel.schema import ArchitectureFile, KeelNode


@dataclass
class NodeRecord:
    """A flattened record of an architecture node with its source path.

    Combines node data with metadata about where the node is stored,
    making it easier to update nodes across multiple architecture files.

    Attributes:
        id: The node's unique identifier.
        name: Human-readable node name.
        paths: File path globs that map to this node.
        path: Path to the architecture file containing this node.
        architecture: The full ArchitectureFile containing this node.
        node: The original KeelNode object.
    """

    id: str
    name: str
    paths: list[str]
    path: Path
    architecture: ArchitectureFile
    node: KeelNode


@dataclass
class DriftResult:
    """Results from architecture drift detection.

    Attributes:
        mapped_files: Changed files that match existing node path patterns.
        unmapped_files: Changed files that don't match any node (potential drift).
        renamed_files: List of (old_path, new_path) tuples for detected renames.
        auto_updated_nodes: Node IDs whose path patterns were auto-updated.
    """

    mapped_files: list[str] = field(default_factory=list)
    unmapped_files: list[str] = field(default_factory=list)
    renamed_files: list[tuple[str, str]] = field(default_factory=list)
    auto_updated_nodes: list[str] = field(default_factory=list)


class FileClassification(BaseModel):
    """AI-generated classification of a file to an architecture node.

    Attributes:
        file_path: Path to the classified file.
        node_id: ID of the matching node, or None if no match.
        confidence: Classification confidence level ("high" or "low").
    """

    file_path: str
    node_id: str | None
    confidence: str = Field(pattern="^(high|low)$")


class BatchClassificationResult(BaseModel):
    """Batch of AI-generated file classifications.

    Attributes:
        classifications: List of individual file classifications.
    """

    classifications: list[FileClassification]


# -- Path matching (map source files to diagram nodes) -------------------------


def normalize_path(path: str) -> str:
    """Normalize a file path for consistent matching.

    Converts backslashes to forward slashes and removes leading ``./``
    for consistent cross-platform path comparison.

    Args:
        path: The file path to normalize.

    Returns:
        Normalized path string with forward slashes and no leading ``./``.

    Example:
        >>> normalize_path(".\\src\\api\\server.py")
        "src/api/server.py"
    """
    return path.replace("\\", "/").lstrip("./")


def glob_matches_path(file_path: str, pattern: str) -> bool:
    """Check if a file path matches a glob pattern.

    Supports standard glob patterns including ``*`` (single segment) and
    ``**`` (multiple segments). Both paths and patterns are normalized
    before matching.

    Args:
        file_path: The file path to check.
        pattern: The glob pattern from a node's paths list.

    Returns:
        True if the file path matches the pattern, False otherwise.

    Example:
        >>> glob_matches_path("src/api/routes/users.py", "src/api/**")
        True
        >>> glob_matches_path("tests/test_api.py", "src/api/**")
        False
    """
    normalized_file = normalize_path(file_path)
    normalized_pattern = normalize_path(pattern)

    if "**" in normalized_pattern:
        regex = "^" + re.escape(normalized_pattern).replace(r"\*\*", ".*").replace(r"\*", "[^/]*") + "$"
        return re.match(regex, normalized_file) is not None

    return fnmatch.fnmatch(normalized_file, normalized_pattern)


def load_node_records(root: Path) -> list[NodeRecord]:
    """Load all architecture nodes as flattened records.

    Reads all architecture files and creates NodeRecord objects for
    each node, making it easy to iterate over all nodes regardless
    of which file they're stored in.

    Args:
        root: Repository root path containing ``.keel/architecture/``.

    Returns:
        List of NodeRecord objects for all nodes across all architecture files.

    Example:
        >>> records = load_node_records(Path("."))
        >>> for r in records:
        ...     print(f"{r.name}: {r.paths}")
    """
    records: list[NodeRecord] = []
    for path in list_architecture_files(root):
        architecture = read_keel_file(path, ArchitectureFile)
        for node in architecture.nodes:
            records.append(
                NodeRecord(
                    id=node.id,
                    name=node.name,
                    paths=list(node.paths),
                    path=path,
                    architecture=architecture,
                    node=node,
                )
            )
    return records


def find_matching_nodes(file_path: str, records: list[NodeRecord]) -> list[NodeRecord]:
    """Find all nodes whose path patterns match a file.

    Args:
        file_path: The file path to match against node patterns.
        records: List of NodeRecord objects to search.

    Returns:
        List of NodeRecord objects whose patterns match the file path.
        May return multiple records if the file matches multiple nodes.

    Example:
        >>> records = load_node_records(Path("."))
        >>> matches = find_matching_nodes("src/api/routes.py", records)
        >>> [m.name for m in matches]
        ["API Gateway"]
    """
    matched: list[NodeRecord] = []
    for record in records:
        if any(glob_matches_path(file_path, pattern) for pattern in record.paths):
            matched.append(record)
    return matched


def file_matches_any_node(file_path: str, records: list[NodeRecord]) -> bool:
    """Check if a file matches any architecture node.

    Args:
        file_path: The file path to check.
        records: List of NodeRecord objects to search.

    Returns:
        True if the file matches at least one node's path patterns.

    Example:
        >>> records = load_node_records(Path("."))
        >>> file_matches_any_node("src/api/routes.py", records)
        True
    """
    return find_matching_nodes(file_path, records) != []


# -- Git diff helpers (used by the drift GitHub Action) ------------------------


def git_diff_names(base: str, head: str, cwd: Path | None = None) -> list[str]:
    """Get list of changed file names between two git refs.

    Uses ``git diff --name-only --find-renames`` to get all files that
    changed between the base and head commits.

    Args:
        base: Base git ref (branch, tag, or commit SHA).
        head: Head git ref to compare against base.
        cwd: Working directory for git command. Defaults to current directory.

    Returns:
        List of changed file paths relative to repository root.

    Raises:
        subprocess.CalledProcessError: If git command fails.

    Example:
        >>> changed = git_diff_names("main", "feature-branch")
        >>> print(changed)
        ["src/api/routes.py", "tests/test_api.py"]
    """
    completed = subprocess.run(
        ["git", "diff", "--name-only", "--find-renames", f"{base}...{head}"],
        capture_output=True,
        text=True,
        check=True,
        cwd=cwd,
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def git_diff_renames(base: str, head: str, cwd: Path | None = None) -> list[tuple[str, str]]:
    """Get list of file renames between two git refs.

    Uses ``git diff --name-status --find-renames`` to detect files that
    were renamed between the base and head commits.

    Args:
        base: Base git ref (branch, tag, or commit SHA).
        head: Head git ref to compare against base.
        cwd: Working directory for git command. Defaults to current directory.

    Returns:
        List of (old_path, new_path) tuples for renamed files.

    Raises:
        subprocess.CalledProcessError: If git command fails.

    Example:
        >>> renames = git_diff_renames("main", "feature-branch")
        >>> print(renames)
        [("src/old_name.py", "src/new_name.py")]
    """
    completed = subprocess.run(
        ["git", "diff", "--name-status", "--find-renames", f"{base}...{head}"],
        capture_output=True,
        text=True,
        check=True,
        cwd=cwd,
    )
    renames: list[tuple[str, str]] = []
    for line in completed.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].startswith("R"):
            renames.append((parts[1], parts[2]))
    return renames


def _update_glob_pattern_for_rename(pattern: str, old_path: str, new_path: str) -> str:
    """Rewrite a glob pattern to account for a file rename.

    When a file is renamed, this function attempts to update glob patterns
    that matched the old path to match the new path. It identifies the
    first differing path segment and replaces it in the pattern.

    Args:
        pattern: The original glob pattern.
        old_path: The old file path before rename.
        new_path: The new file path after rename.

    Returns:
        Updated pattern that should match the new path, or the original
        pattern if no update was possible.

    Example:
        >>> _update_glob_pattern_for_rename("src/api/**", "src/api/v1/routes.py", "src/api/v2/routes.py")
        "src/api/**"  # Pattern still works, no change needed
    """
    old_parts = old_path.split("/")
    new_parts = new_path.split("/")

    diff_idx = 0
    for index in range(min(len(old_parts), len(new_parts))):
        if old_parts[index] != new_parts[index]:
            diff_idx = index
            break
    else:
        diff_idx = min(len(old_parts), len(new_parts))

    if diff_idx >= len(old_parts) or diff_idx >= len(new_parts):
        return pattern

    old_segment = old_parts[diff_idx]
    new_segment = new_parts[diff_idx]
    if old_segment in pattern:
        return pattern.replace(old_segment, new_segment, 1)
    return pattern


def update_paths_for_rename(
    root: Path,
    records: list[NodeRecord],
    old_path: str,
    new_path: str,
) -> list[str]:
    """Update node path globs to account for a file rename.

    Finds all nodes whose patterns matched the old path and updates
    their patterns to match the new path. For exact path matches,
    replaces the path. For glob patterns, attempts to update the
    pattern or adds the new path explicitly.

    Args:
        root: Repository root path containing ``.keel/architecture/``.
        records: List of NodeRecord objects to potentially update.
        old_path: The old file path before rename.
        new_path: The new file path after rename.

    Returns:
        List of node IDs that were updated.

    Example:
        >>> records = load_node_records(Path("."))
        >>> updated = update_paths_for_rename(Path("."), records, "src/old.py", "src/new.py")
        >>> print(updated)
        ["node_api"]
    """
    updated_ids: list[str] = []
    old_norm = normalize_path(old_path)
    new_norm = normalize_path(new_path)

    files_by_arch_path: dict[Path, ArchitectureFile] = {}
    for record in records:
        if record.path not in files_by_arch_path:
            files_by_arch_path[record.path] = record.architecture.model_copy(deep=True)

    for record in records:
        if not any(glob_matches_path(old_norm, pattern) for pattern in record.paths):
            continue

        arch = files_by_arch_path[record.path]
        for index, node in enumerate(arch.nodes):
            if node.id != record.id:
                continue
            new_patterns = list(node.paths)
            for pattern_index, pattern in enumerate(new_patterns):
                if not glob_matches_path(old_norm, pattern):
                    continue
                if "*" not in pattern:
                    new_patterns[pattern_index] = new_norm
                else:
                    updated_pattern = _update_glob_pattern_for_rename(pattern, old_norm, new_norm)
                    if updated_pattern != pattern:
                        new_patterns[pattern_index] = updated_pattern
                    elif new_norm not in new_patterns:
                        new_patterns.append(new_norm)
            arch.nodes[index] = node.model_copy(update={"paths": sorted(set(new_patterns))})
            write_keel_file(record.path, arch)
            updated_ids.append(node.id)
            break

    return updated_ids


# -- Core drift detection on a PR file list ----------------------------------


def detect_drift(
    root: Path,
    changed_files: list[str],
    renames: list[tuple[str, str]],
) -> DriftResult:
    """Detect architecture drift from changed files.

    Analyzes a list of changed files against architecture node path
    patterns. Files that don't match any pattern are flagged as
    potential architecture drift. File renames are handled by
    auto-updating node patterns where possible.

    Args:
        root: Repository root path containing ``.keel/architecture/``.
        changed_files: List of changed file paths from a git diff.
        renames: List of (old_path, new_path) tuples for renamed files.

    Returns:
        DriftResult containing categorized files and auto-update information.

    Example:
        >>> changed = ["src/api/routes.py", "src/new_module/handler.py"]
        >>> renames = []
        >>> result = detect_drift(Path("."), changed, renames)
        >>> print(result.unmapped_files)
        ["src/new_module/handler.py"]
    """
    records = load_node_records(root)
    result = DriftResult()

    renamed_new_paths = {new for _, new in renames}
    for old_path, new_path in renames:
        result.renamed_files.append((old_path, new_path))
        updated = update_paths_for_rename(root, records, old_path, new_path)
        result.auto_updated_nodes.extend(updated)
        records = load_node_records(root)

    for file_path in changed_files:
        if file_path in renamed_new_paths:
            continue
        if file_matches_any_node(file_path, records):
            result.mapped_files.append(file_path)
        else:
            result.unmapped_files.append(file_path)

    return result


def apply_high_confidence_classifications(
    root: Path,
    classifications: list[FileClassification],
) -> list[str]:
    """Apply AI-generated file classifications to architecture nodes.

    For each high-confidence classification, adds the file path to
    the corresponding node's path patterns. Low-confidence
    classifications are ignored.

    Args:
        root: Repository root path containing ``.keel/architecture/``.
        classifications: List of FileClassification objects from AI.

    Returns:
        List of node IDs that were updated.

    Example:
        >>> classifications = [
        ...     FileClassification(file_path="src/new.py", node_id="node_api", confidence="high")
        ... ]
        >>> updated = apply_high_confidence_classifications(Path("."), classifications)
        >>> print(updated)
        ["node_api"]
    """
    updated_nodes: list[str] = []
    records = load_node_records(root)

    for item in classifications:
        if item.confidence != "high" or not item.node_id:
            continue
        record = next((entry for entry in records if entry.id == item.node_id), None)
        if record is None:
            continue

        arch = read_keel_file(record.path, ArchitectureFile)
        for index, node in enumerate(arch.nodes):
            if node.id != item.node_id:
                continue
            patterns = list(node.paths)
            normalized = normalize_path(item.file_path)
            if normalized not in patterns:
                patterns.append(normalized)
            arch.nodes[index] = node.model_copy(update={"paths": sorted(set(patterns))})
            write_keel_file(record.path, arch)
            updated_nodes.append(node.id)
            break

    return updated_nodes


def build_classification_prompt(unmapped_files: list[str], records: list[NodeRecord]) -> str:
    """Build a prompt for AI classification of unmapped files.

    Creates a structured prompt asking the AI to classify unmapped
    files against existing architecture nodes.

    Args:
        unmapped_files: List of file paths that don't match any node.
        records: List of NodeRecord objects representing available nodes.

    Returns:
        A formatted prompt string for the AI classification task.

    Example:
        >>> records = load_node_records(Path("."))
        >>> prompt = build_classification_prompt(["src/new.py"], records)
        >>> print(prompt[:50])
        "Classify unmapped changed files against existing..."
    """
    nodes = [{"id": record.id, "name": record.name, "paths": record.paths} for record in records]
    return f"""Classify unmapped changed files against existing architecture nodes.

Unmapped files:
{json.dumps(unmapped_files, indent=2)}

Existing nodes:
{json.dumps(nodes, indent=2)}

Return JSON only:
{{
  "classifications": [
    {{"file_path": "path/to/file.py", "node_id": "node_api", "confidence": "high"}}
  ]
}}

Rules:
- node_id must be an existing node id or null when genuinely new architecture is implied.
- confidence must be "high" or "low".
- Return one entry per unmapped file.
- Return JSON only, no markdown fences.
"""

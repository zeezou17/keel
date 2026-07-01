"""Deterministic architecture drift detection via path globs."""

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
    id: str
    name: str
    paths: list[str]
    path: Path
    architecture: ArchitectureFile
    node: KeelNode


@dataclass
class DriftResult:
    mapped_files: list[str] = field(default_factory=list)
    unmapped_files: list[str] = field(default_factory=list)
    renamed_files: list[tuple[str, str]] = field(default_factory=list)
    auto_updated_nodes: list[str] = field(default_factory=list)


class FileClassification(BaseModel):
    file_path: str
    node_id: str | None
    confidence: str = Field(pattern="^(high|low)$")


class BatchClassificationResult(BaseModel):
    classifications: list[FileClassification]


# -- Path matching (map source files to diagram nodes) -------------------------


def normalize_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def glob_matches_path(file_path: str, pattern: str) -> bool:
    """Return True when `file_path` matches a node `paths` glob."""
    normalized_file = normalize_path(file_path)
    normalized_pattern = normalize_path(pattern)

    if "**" in normalized_pattern:
        regex = "^" + re.escape(normalized_pattern).replace(r"\*\*", ".*").replace(r"\*", "[^/]*") + "$"
        return re.match(regex, normalized_file) is not None

    return fnmatch.fnmatch(normalized_file, normalized_pattern)


def load_node_records(root: Path) -> list[NodeRecord]:
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
    matched: list[NodeRecord] = []
    for record in records:
        if any(glob_matches_path(file_path, pattern) for pattern in record.paths):
            matched.append(record)
    return matched


def file_matches_any_node(file_path: str, records: list[NodeRecord]) -> bool:
    return find_matching_nodes(file_path, records) != []


# -- Git diff helpers (used by the drift GitHub Action) ------------------------


def git_diff_names(base: str, head: str, cwd: Path | None = None) -> list[str]:
    completed = subprocess.run(
        ["git", "diff", "--name-only", "--find-renames", f"{base}...{head}"],
        capture_output=True,
        text=True,
        check=True,
        cwd=cwd,
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def git_diff_renames(base: str, head: str, cwd: Path | None = None) -> list[tuple[str, str]]:
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
    """Rewrite a glob when a renamed file still matches the old pattern."""
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
    """Update node globs for a rename and return updated node ids."""
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
    """Append high-confidence file paths to node globs."""
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

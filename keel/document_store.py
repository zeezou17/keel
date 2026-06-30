"""CRUD helpers for requirements, ADRs, and characteristics."""

from __future__ import annotations

import re
from pathlib import Path

from keel.architecture_store import find_node_location, list_architecture_files
from keel.file_io import read_keel_file, read_keel_markdown, write_keel_file, write_keel_markdown
from keel.schema import ADR, ADRStatus, ArchitectureFile, Characteristic, Requirement, ReqStatus

REQUIREMENTS_DIR = Path(".keel") / "requirements"
DECISIONS_DIR = Path(".keel") / "decisions"
CHARACTERISTICS_DIR = Path(".keel") / "characteristics"


class DocumentNotFoundError(FileNotFoundError):
    """Raised when a Keel document cannot be found."""


def _next_document_id(prefix: str, directory: Path, extension: str) -> str:
    if not directory.exists():
        return f"{prefix}001"

    numbers: list[int] = []
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+){re.escape(extension)}$")
    for path in directory.iterdir():
        match = pattern.match(path.name)
        if match:
            numbers.append(int(match.group(1)))
    return f"{prefix}{max(numbers, default=0) + 1:03d}"


def _requirement_path(root: Path, req_id: str) -> Path:
    return root / REQUIREMENTS_DIR / f"{req_id}.md"


def _adr_path(root: Path, adr_id: str) -> Path:
    return root / DECISIONS_DIR / f"{adr_id}.md"


def _characteristic_path(root: Path, char_id: str) -> Path:
    return root / CHARACTERISTICS_DIR / f"{char_id}.yml"


def list_requirements(root: Path) -> list[tuple[Requirement, str]]:
    directory = root / REQUIREMENTS_DIR
    if not directory.exists():
        return []
    items: list[tuple[Requirement, str]] = []
    for path in sorted(directory.glob("REQ-*.md")):
        req, body = read_keel_markdown(path, Requirement)
        items.append((req, body))
    return items


def get_requirement(root: Path, req_id: str) -> tuple[Requirement, str]:
    path = _requirement_path(root, req_id)
    if not path.exists():
        raise DocumentNotFoundError(req_id)
    return read_keel_markdown(path, Requirement)


def create_requirement(
    root: Path,
    title: str,
    description: str = "",
    acceptance_criteria: list[str] | None = None,
) -> tuple[Requirement, str]:
    directory = root / REQUIREMENTS_DIR
    req_id = _next_document_id("REQ-", directory, ".md")
    requirement = Requirement(
        id=req_id,
        title=title,
        status=ReqStatus.draft,
        acceptance_criteria=acceptance_criteria or [],
    )
    path = _requirement_path(root, req_id)
    write_keel_markdown(path, requirement, description)
    return requirement, description


def save_requirement(root: Path, requirement: Requirement, body: str) -> Requirement:
    path = _requirement_path(root, requirement.id)
    if not path.exists():
        raise DocumentNotFoundError(requirement.id)

    previous, _ = read_keel_markdown(path, Requirement)
    write_keel_markdown(path, requirement, body)
    _sync_requirement_links(root, requirement.id, previous.linked_node_ids, requirement.linked_node_ids)
    return requirement


def delete_requirement(root: Path, req_id: str) -> None:
    path = _requirement_path(root, req_id)
    if not path.exists():
        raise DocumentNotFoundError(req_id)
    requirement, _ = read_keel_markdown(path, Requirement)
    _sync_requirement_links(root, req_id, requirement.linked_node_ids, [])
    path.unlink()


def _sync_requirement_links(
    root: Path,
    req_id: str,
    previous_node_ids: list[str],
    next_node_ids: list[str],
) -> None:
    removed = set(previous_node_ids) - set(next_node_ids)
    added = set(next_node_ids) - set(previous_node_ids)

    for node_id in removed | added:
        try:
            path, arch, node = find_node_location(root, node_id)
        except KeyError:
            continue

        req_ids = list(node.req_ids)
        if node_id in removed and req_id in req_ids:
            req_ids.remove(req_id)
        if node_id in added and req_id not in req_ids:
            req_ids.append(req_id)

        updated = node.model_copy(update={"req_ids": req_ids})
        arch.nodes = [updated if item.id == node_id else item for item in arch.nodes]
        write_keel_file(path, arch)


def list_adrs(root: Path) -> list[tuple[ADR, str]]:
    directory = root / DECISIONS_DIR
    if not directory.exists():
        return []
    items: list[tuple[ADR, str]] = []
    for path in sorted(directory.glob("ADR-*.md")):
        adr, body = read_keel_markdown(path, ADR)
        items.append((adr, body))
    return items


def get_adr(root: Path, adr_id: str) -> tuple[ADR, str]:
    path = _adr_path(root, adr_id)
    if not path.exists():
        raise DocumentNotFoundError(adr_id)
    return read_keel_markdown(path, ADR)


def create_adr(root: Path, title: str, body: str | None = None) -> tuple[ADR, str]:
    directory = root / DECISIONS_DIR
    adr_id = _next_document_id("ADR-", directory, ".md")
    adr = ADR(id=adr_id, title=title, status=ADRStatus.proposed)
    default_body = body or "## Context\n\n## Decision\n\n## Consequences\n"
    write_keel_markdown(_adr_path(root, adr_id), adr, default_body)
    return adr, default_body


def save_adr(root: Path, adr: ADR, body: str) -> ADR:
    path = _adr_path(root, adr.id)
    if not path.exists():
        raise DocumentNotFoundError(adr.id)

    previous, _ = read_keel_markdown(path, ADR)
    write_keel_markdown(path, adr, body)
    _sync_adr_links(root, adr.id, previous.linked_node_ids, adr.linked_node_ids)
    return adr


def delete_adr(root: Path, adr_id: str) -> None:
    path = _adr_path(root, adr_id)
    if not path.exists():
        raise DocumentNotFoundError(adr_id)
    adr, _ = read_keel_markdown(path, ADR)
    _sync_adr_links(root, adr_id, adr.linked_node_ids, [])
    path.unlink()


def _sync_adr_links(
    root: Path,
    adr_id: str,
    previous_node_ids: list[str],
    next_node_ids: list[str],
) -> None:
    removed = set(previous_node_ids) - set(next_node_ids)
    added = set(next_node_ids) - set(previous_node_ids)

    for node_id in removed | added:
        try:
            path, arch, node = find_node_location(root, node_id)
        except KeyError:
            continue

        adr_ids = list(node.adr_ids)
        if node_id in removed and adr_id in adr_ids:
            adr_ids.remove(adr_id)
        if node_id in added and adr_id not in adr_ids:
            adr_ids.append(adr_id)

        updated = node.model_copy(update={"adr_ids": adr_ids})
        arch.nodes = [updated if item.id == node_id else item for item in arch.nodes]
        write_keel_file(path, arch)


def list_characteristics(root: Path) -> list[Characteristic]:
    directory = root / CHARACTERISTICS_DIR
    if not directory.exists():
        return []
    return [read_keel_file(path, Characteristic) for path in sorted(directory.glob("CHAR-*.yml"))]


def get_characteristic(root: Path, char_id: str) -> Characteristic:
    path = _characteristic_path(root, char_id)
    if not path.exists():
        raise DocumentNotFoundError(char_id)
    return read_keel_file(path, Characteristic)


def create_characteristic(root: Path, characteristic: Characteristic) -> Characteristic:
    directory = root / CHARACTERISTICS_DIR
    if characteristic.id and characteristic.id.startswith("CHAR-"):
        char_id = characteristic.id
    else:
        char_id = _next_document_id("CHAR-", directory, ".yml")
        characteristic = characteristic.model_copy(update={"id": char_id})

    path = _characteristic_path(root, char_id)
    write_keel_file(path, characteristic)
    return characteristic


def save_characteristic(root: Path, characteristic: Characteristic) -> Characteristic:
    path = _characteristic_path(root, characteristic.id)
    if not path.exists():
        raise DocumentNotFoundError(characteristic.id)
    write_keel_file(path, characteristic)
    return characteristic


def delete_characteristic(root: Path, char_id: str) -> None:
    path = _characteristic_path(root, char_id)
    if not path.exists():
        raise DocumentNotFoundError(char_id)
    path.unlink()


def all_node_ids(root: Path) -> list[str]:
    node_ids: list[str] = []
    for path in list_architecture_files(root):
        arch = read_keel_file(path, ArchitectureFile)
        node_ids.extend(node.id for node in arch.nodes)
    return node_ids

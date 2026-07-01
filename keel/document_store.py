"""CRUD helpers for requirements, ADRs, and characteristics.

This module provides storage operations for Keel documents:
    - Requirements: ``.keel/requirements/REQ-*.md``
    - ADRs: ``.keel/decisions/ADR-*.md``
    - Characteristics: ``.keel/characteristics/CHAR-*.yml``

Requirements and ADRs are stored as Markdown files with YAML frontmatter.
Characteristics are stored as plain YAML files.

When requirements or ADRs are linked to architecture nodes, this module
also handles syncing those links bidirectionally (updating both the
document and the node's linked IDs).

Example:
    Creating and managing requirements::

        from pathlib import Path
        from keel.document_store import create_requirement, save_requirement

        req, body = create_requirement(Path("."), "User login", "Users can log in...")
        print(f"Created {req.id}")

        req.status = ReqStatus.approved
        save_requirement(Path("."), req, body)
"""

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
    """Raised when a Keel document cannot be found.

    This exception is raised when attempting to access, update, or delete
    a requirement, ADR, or characteristic that doesn't exist.
    """


# -- Shared ID and path helpers ----------------------------------------------


def _next_document_id(prefix: str, directory: Path, extension: str) -> str:
    """Generate the next sequential document ID.

    Scans existing files to find the highest number and returns the next one.

    Args:
        prefix: ID prefix (e.g., "REQ-", "ADR-", "CHAR-").
        directory: Directory containing the document files.
        extension: File extension (e.g., ".md", ".yml").

    Returns:
        Next ID in format "{prefix}NNN" (e.g., "REQ-001").
    """
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
    """Get the file path for a requirement.

    Args:
        root: Repository root path.
        req_id: Requirement ID (e.g., "REQ-001").

    Returns:
        Path to the requirement Markdown file.
    """
    return root / REQUIREMENTS_DIR / f"{req_id}.md"


def _adr_path(root: Path, adr_id: str) -> Path:
    """Get the file path for an ADR.

    Args:
        root: Repository root path.
        adr_id: ADR ID (e.g., "ADR-001").

    Returns:
        Path to the ADR Markdown file.
    """
    return root / DECISIONS_DIR / f"{adr_id}.md"


def _characteristic_path(root: Path, char_id: str) -> Path:
    """Get the file path for a characteristic.

    Args:
        root: Repository root path.
        char_id: Characteristic ID (e.g., "CHAR-001").

    Returns:
        Path to the characteristic YAML file.
    """
    return root / CHARACTERISTICS_DIR / f"{char_id}.yml"


# -- Requirements ------------------------------------------------------------


def list_requirements(root: Path) -> list[tuple[Requirement, str]]:
    """List all requirements in the repository.

    Args:
        root: Repository root path containing ``.keel/requirements/``.

    Returns:
        List of (Requirement, body) tuples, sorted by ID.

    Example:
        >>> for req, body in list_requirements(Path(".")):
        ...     print(f"{req.id}: {req.title}")
    """
    directory = root / REQUIREMENTS_DIR
    if not directory.exists():
        return []
    items: list[tuple[Requirement, str]] = []
    for path in sorted(directory.glob("REQ-*.md")):
        req, body = read_keel_markdown(path, Requirement)
        items.append((req, body))
    return items


def get_requirement(root: Path, req_id: str) -> tuple[Requirement, str]:
    """Get a single requirement by ID.

    Args:
        root: Repository root path.
        req_id: Requirement ID (e.g., "REQ-001").

    Returns:
        Tuple of (Requirement, body_string).

    Raises:
        DocumentNotFoundError: If the requirement doesn't exist.

    Example:
        >>> req, body = get_requirement(Path("."), "REQ-001")
        >>> print(req.title)
    """
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
    """Create a new requirement.

    Generates a sequential ID and creates the Markdown file with
    YAML frontmatter.

    Args:
        root: Repository root path.
        title: Short title for the requirement.
        description: Detailed description (becomes the markdown body).
        acceptance_criteria: Optional list of acceptance criteria.

    Returns:
        Tuple of (Requirement, body_string).

    Example:
        >>> req, body = create_requirement(
        ...     Path("."),
        ...     title="User login",
        ...     description="Users should be able to log in with email/password.",
        ... )
        >>> print(req.id)
        "REQ-001"
    """
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
    """Save changes to an existing requirement.

    Also syncs linked_node_ids bidirectionally with architecture nodes.

    Args:
        root: Repository root path.
        requirement: Updated Requirement model.
        body: Updated markdown body content.

    Returns:
        The saved Requirement.

    Raises:
        DocumentNotFoundError: If the requirement doesn't exist.

    Example:
        >>> req, body = get_requirement(Path("."), "REQ-001")
        >>> req.status = ReqStatus.approved
        >>> save_requirement(Path("."), req, body)
    """
    path = _requirement_path(root, requirement.id)
    if not path.exists():
        raise DocumentNotFoundError(requirement.id)

    previous, _ = read_keel_markdown(path, Requirement)
    write_keel_markdown(path, requirement, body)
    _sync_requirement_links(root, requirement.id, previous.linked_node_ids, requirement.linked_node_ids)
    return requirement


def delete_requirement(root: Path, req_id: str) -> None:
    """Delete a requirement and clean up its node links.

    Removes the requirement file and updates any linked architecture
    nodes to remove the requirement from their req_ids lists.

    Args:
        root: Repository root path.
        req_id: Requirement ID to delete.

    Raises:
        DocumentNotFoundError: If the requirement doesn't exist.

    Example:
        >>> delete_requirement(Path("."), "REQ-001")
    """
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
    """Sync requirement links bidirectionally with architecture nodes.

    When a requirement's linked_node_ids change, updates the corresponding
    nodes' req_ids lists to maintain bidirectional consistency.

    Args:
        root: Repository root path.
        req_id: The requirement ID being linked/unlinked.
        previous_node_ids: Previous list of linked node IDs.
        next_node_ids: New list of linked node IDs.
    """
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


# -- Architecture Decision Records (ADRs) --------------------------------------


def list_adrs(root: Path) -> list[tuple[ADR, str]]:
    """List all ADRs in the repository.

    Args:
        root: Repository root path containing ``.keel/decisions/``.

    Returns:
        List of (ADR, body) tuples, sorted by ID.

    Example:
        >>> for adr, body in list_adrs(Path(".")):
        ...     print(f"{adr.id}: {adr.title}")
    """
    directory = root / DECISIONS_DIR
    if not directory.exists():
        return []
    items: list[tuple[ADR, str]] = []
    for path in sorted(directory.glob("ADR-*.md")):
        adr, body = read_keel_markdown(path, ADR)
        items.append((adr, body))
    return items


def get_adr(root: Path, adr_id: str) -> tuple[ADR, str]:
    """Get a single ADR by ID.

    Args:
        root: Repository root path.
        adr_id: ADR ID (e.g., "ADR-001").

    Returns:
        Tuple of (ADR, body_string).

    Raises:
        DocumentNotFoundError: If the ADR doesn't exist.

    Example:
        >>> adr, body = get_adr(Path("."), "ADR-001")
        >>> print(adr.title)
    """
    path = _adr_path(root, adr_id)
    if not path.exists():
        raise DocumentNotFoundError(adr_id)
    return read_keel_markdown(path, ADR)


def create_adr(root: Path, title: str, body: str | None = None) -> tuple[ADR, str]:
    """Create a new ADR.

    Generates a sequential ID and creates the Markdown file with
    YAML frontmatter. If no body is provided, uses a default template
    with Context, Decision, and Consequences sections.

    Args:
        root: Repository root path.
        title: Short title describing the decision.
        body: Optional markdown body. Defaults to ADR template.

    Returns:
        Tuple of (ADR, body_string).

    Example:
        >>> adr, body = create_adr(Path("."), "Use PostgreSQL for persistence")
        >>> print(adr.id)
        "ADR-001"
    """
    directory = root / DECISIONS_DIR
    adr_id = _next_document_id("ADR-", directory, ".md")
    adr = ADR(id=adr_id, title=title, status=ADRStatus.proposed)
    default_body = body or "## Context\n\n## Decision\n\n## Consequences\n"
    write_keel_markdown(_adr_path(root, adr_id), adr, default_body)
    return adr, default_body


def save_adr(root: Path, adr: ADR, body: str) -> ADR:
    """Save changes to an existing ADR.

    Also syncs linked_node_ids bidirectionally with architecture nodes.

    Args:
        root: Repository root path.
        adr: Updated ADR model.
        body: Updated markdown body content.

    Returns:
        The saved ADR.

    Raises:
        DocumentNotFoundError: If the ADR doesn't exist.

    Example:
        >>> adr, body = get_adr(Path("."), "ADR-001")
        >>> adr.status = ADRStatus.accepted
        >>> save_adr(Path("."), adr, body)
    """
    path = _adr_path(root, adr.id)
    if not path.exists():
        raise DocumentNotFoundError(adr.id)

    previous, _ = read_keel_markdown(path, ADR)
    write_keel_markdown(path, adr, body)
    _sync_adr_links(root, adr.id, previous.linked_node_ids, adr.linked_node_ids)
    return adr


def delete_adr(root: Path, adr_id: str) -> None:
    """Delete an ADR and clean up its node links.

    Removes the ADR file and updates any linked architecture nodes
    to remove the ADR from their adr_ids lists.

    Args:
        root: Repository root path.
        adr_id: ADR ID to delete.

    Raises:
        DocumentNotFoundError: If the ADR doesn't exist.

    Example:
        >>> delete_adr(Path("."), "ADR-001")
    """
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
    """Sync ADR links bidirectionally with architecture nodes.

    When an ADR's linked_node_ids change, updates the corresponding
    nodes' adr_ids lists to maintain bidirectional consistency.

    Args:
        root: Repository root path.
        adr_id: The ADR ID being linked/unlinked.
        previous_node_ids: Previous list of linked node IDs.
        next_node_ids: New list of linked node IDs.
    """
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


# -- Quality characteristics (non-functional requirements) ---------------------


def list_characteristics(root: Path) -> list[Characteristic]:
    """List all quality characteristics in the repository.

    Args:
        root: Repository root path containing ``.keel/characteristics/``.

    Returns:
        List of Characteristic objects, sorted by ID.

    Example:
        >>> for char in list_characteristics(Path(".")):
        ...     print(f"{char.id}: {char.name} ({char.priority})")
    """
    directory = root / CHARACTERISTICS_DIR
    if not directory.exists():
        return []
    return [read_keel_file(path, Characteristic) for path in sorted(directory.glob("CHAR-*.yml"))]


def get_characteristic(root: Path, char_id: str) -> Characteristic:
    """Get a single characteristic by ID.

    Args:
        root: Repository root path.
        char_id: Characteristic ID (e.g., "CHAR-001").

    Returns:
        The Characteristic object.

    Raises:
        DocumentNotFoundError: If the characteristic doesn't exist.

    Example:
        >>> char = get_characteristic(Path("."), "CHAR-001")
        >>> print(char.name)
    """
    path = _characteristic_path(root, char_id)
    if not path.exists():
        raise DocumentNotFoundError(char_id)
    return read_keel_file(path, Characteristic)


def create_characteristic(root: Path, characteristic: Characteristic) -> Characteristic:
    """Create a new quality characteristic.

    If the characteristic has a valid ID (starting with "CHAR-"), uses it.
    Otherwise, generates a sequential ID.

    Args:
        root: Repository root path.
        characteristic: Characteristic model to create.

    Returns:
        The created Characteristic (may have updated ID).

    Example:
        >>> char = Characteristic(
        ...     id="",
        ...     name="Response Time",
        ...     priority=Priority.high,
        ...     scenario="API responds in < 200ms for 95th percentile",
        ... )
        >>> created = create_characteristic(Path("."), char)
        >>> print(created.id)
        "CHAR-001"
    """
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
    """Save changes to an existing characteristic.

    Args:
        root: Repository root path.
        characteristic: Updated Characteristic model.

    Returns:
        The saved Characteristic.

    Raises:
        DocumentNotFoundError: If the characteristic doesn't exist.

    Example:
        >>> char = get_characteristic(Path("."), "CHAR-001")
        >>> char.priority = Priority.medium
        >>> save_characteristic(Path("."), char)
    """
    path = _characteristic_path(root, characteristic.id)
    if not path.exists():
        raise DocumentNotFoundError(characteristic.id)
    write_keel_file(path, characteristic)
    return characteristic


def delete_characteristic(root: Path, char_id: str) -> None:
    """Delete a characteristic.

    Args:
        root: Repository root path.
        char_id: Characteristic ID to delete.

    Raises:
        DocumentNotFoundError: If the characteristic doesn't exist.

    Example:
        >>> delete_characteristic(Path("."), "CHAR-001")
    """
    path = _characteristic_path(root, char_id)
    if not path.exists():
        raise DocumentNotFoundError(char_id)
    path.unlink()


def all_node_ids(root: Path) -> list[str]:
    """Get all node IDs from all architecture files.

    Collects node IDs from all C1, C2, and C3 architecture files.

    Args:
        root: Repository root path.

    Returns:
        List of all node IDs in the repository.

    Example:
        >>> ids = all_node_ids(Path("."))
        >>> print(ids)
        ["node_api", "node_db", "node_cache"]
    """
    node_ids: list[str] = []
    for path in list_architecture_files(root):
        arch = read_keel_file(path, ArchitectureFile)
        node_ids.extend(node.id for node in arch.nodes)
    return node_ids

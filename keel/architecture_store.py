"""Read/write helpers for ``.keel/architecture/`` files.

This module provides CRUD operations for C4 architecture diagrams stored
as JSON files under ``.keel/architecture/``. It handles:
    - Path resolution for C1, C2, and C3 diagram files
    - Loading and saving architecture files
    - Node CRUD operations (add, update, delete)
    - Node lookup across all architecture files

File naming conventions:
    - C1 Context: ``c1-context.json``
    - C2 Containers: ``c2-containers.json``
    - C3 Components: ``c3-{container-slug}.json``

Example:
    Loading and modifying an architecture diagram::

        from pathlib import Path
        from keel.architecture_store import load_architecture, save_architecture, architecture_path

        arch = load_architecture(Path("."), level=2)
        arch.nodes.append(new_node)
        save_architecture(architecture_path(Path("."), level=2), arch)
"""

from __future__ import annotations

import re
from pathlib import Path

from keel.file_io import read_keel_file, write_keel_file
from keel.schema import ArchitectureFile, KeelEdge, KeelNode, NodeLevel

ARCHITECTURE_DIR = Path(".keel") / "architecture"


class ArchitectureNotFoundError(FileNotFoundError):
    """Raised when an architecture file cannot be located.

    This exception is raised when attempting to load an architecture
    file that doesn't exist on disk.
    """


class NodeNotFoundError(KeyError):
    """Raised when a node ID is not present in any architecture file.

    This exception is raised when searching for a node by ID fails
    across all architecture files.
    """


# -- Path resolution (C1/C2/C3 file names on disk) ---------------------------


def architecture_dir(root: Path) -> Path:
    """Get the architecture directory path.

    Args:
        root: Repository root path.

    Returns:
        Path to ``.keel/architecture/`` directory.
    """
    return root / ARCHITECTURE_DIR


def container_slug(container_id: str) -> str:
    """Convert a container ID to a filename-safe slug.

    Removes the ``node_`` prefix to create shorter, cleaner filenames.

    Args:
        container_id: The container node ID (e.g., "node_api-gateway").

    Returns:
        Slug suitable for filenames (e.g., "api-gateway").

    Example:
        >>> container_slug("node_api-gateway")
        "api-gateway"
    """
    return container_id.removeprefix("node_")


def architecture_path(root: Path, level: int, container_id: str | None = None) -> Path:
    """Get the file path for an architecture diagram.

    Args:
        root: Repository root path.
        level: C4 diagram level (1, 2, or 3).
        container_id: Required for level 3, the parent container ID.

    Returns:
        Path to the architecture JSON file.

    Raises:
        ValueError: If level is 3 and container_id is not provided,
            or if level is not 1, 2, or 3.

    Example:
        >>> architecture_path(Path("."), level=1)
        PosixPath(".keel/architecture/c1-context.json")
        >>> architecture_path(Path("."), level=3, container_id="node_api")
        PosixPath(".keel/architecture/c3-api.json")
    """
    arch_dir = architecture_dir(root)
    if level == 1:
        return arch_dir / "c1-context.json"
    if level == 2:
        return arch_dir / "c2-containers.json"
    if level == 3:
        if not container_id:
            raise ValueError("container_id is required for level 3 architecture files.")
        return arch_dir / f"c3-{container_slug(container_id)}.json"
    raise ValueError(f"Unsupported architecture level: {level}")


# -- Load/save whole diagram files -------------------------------------------


def load_architecture(
    root: Path,
    level: int,
    container_id: str | None = None,
) -> ArchitectureFile:
    """Load an architecture diagram from disk.

    Args:
        root: Repository root path.
        level: C4 diagram level (1, 2, or 3).
        container_id: Required for level 3, the parent container ID.

    Returns:
        Parsed ArchitectureFile model.

    Raises:
        ArchitectureNotFoundError: If the file doesn't exist.
        ValueError: If level/container_id are invalid.

    Example:
        >>> arch = load_architecture(Path("."), level=2)
        >>> print(len(arch.nodes))
        5
    """
    path = architecture_path(root, level, container_id)
    if not path.exists():
        raise ArchitectureNotFoundError(f"Architecture file not found: {path}")
    return read_keel_file(path, ArchitectureFile)


def save_architecture(path: Path, model: ArchitectureFile) -> None:
    """Save an architecture diagram to disk.

    Args:
        path: Path to save the file to.
        model: ArchitectureFile model to save.

    Raises:
        ValidationError: If the model is invalid.
        OSError: If file write fails.

    Example:
        >>> save_architecture(architecture_path(Path("."), 2), arch)
    """
    write_keel_file(path, model)


def list_architecture_files(root: Path) -> list[Path]:
    """List all architecture JSON files in the repository.

    Args:
        root: Repository root path.

    Returns:
        Sorted list of paths to all architecture files.

    Example:
        >>> files = list_architecture_files(Path("."))
        >>> [f.name for f in files]
        ["c1-context.json", "c2-containers.json", "c3-api.json"]
    """
    arch_dir = architecture_dir(root)
    if not arch_dir.exists():
        return []
    return sorted(arch_dir.glob("*.json"))


# -- Node lookup and CRUD (used by API and sparring actions) -----------------


def find_node_location(
    root: Path,
    node_id: str,
) -> tuple[Path, ArchitectureFile, KeelNode]:
    """Find a node across all architecture files.

    Searches all architecture files (C1, C2, C3) for a node with
    the given ID.

    Args:
        root: Repository root path.
        node_id: The node ID to find.

    Returns:
        Tuple of (file_path, architecture, node).

    Raises:
        NodeNotFoundError: If no node with that ID exists.

    Example:
        >>> path, arch, node = find_node_location(Path("."), "node_api")
        >>> print(node.name)
        "API Gateway"
    """
    for path in list_architecture_files(root):
        arch = read_keel_file(path, ArchitectureFile)
        for node in arch.nodes:
            if node.id == node_id:
                return path, arch, node
    raise NodeNotFoundError(node_id)


def add_node(root: Path, level: int, node: KeelNode, container_id: str | None = None) -> ArchitectureFile:
    """Add a new node to an architecture diagram.

    If the architecture file doesn't exist, creates it with the new node.

    Args:
        root: Repository root path.
        level: C4 level to add the node to (1, 2, or 3).
        node: The KeelNode to add.
        container_id: For C3 nodes, the parent container ID.

    Returns:
        The updated ArchitectureFile.

    Raises:
        ValueError: If a node with the same ID already exists.

    Example:
        >>> new_node = KeelNode(id="node_cache", type=NodeType.container, ...)
        >>> arch = add_node(Path("."), level=2, node=new_node)
    """
    path = architecture_path(root, level, container_id or node.parent_id)
    if path.exists():
        arch = read_keel_file(path, ArchitectureFile)
    else:
        arch = ArchitectureFile(
            level=NodeLevel(level),
            container_id=container_id or node.parent_id if level == 3 else None,
            nodes=[],
            edges=[],
        )

    if any(existing.id == node.id for existing in arch.nodes):
        raise ValueError(f"Node id already exists: {node.id}")

    arch.nodes.append(node)
    write_keel_file(path, arch)
    return arch


def update_node(root: Path, node_id: str, updates: KeelNode) -> ArchitectureFile:
    """Update an existing node in an architecture diagram.

    Args:
        root: Repository root path.
        node_id: ID of the node to update.
        updates: New KeelNode values (replaces the entire node).

    Returns:
        The updated ArchitectureFile.

    Raises:
        NodeNotFoundError: If no node with that ID exists.

    Example:
        >>> updated_node = node.model_copy(update={"description": "New desc"})
        >>> arch = update_node(Path("."), "node_api", updated_node)
    """
    path, arch, _ = find_node_location(root, node_id)
    arch.nodes = [updates if node.id == node_id else node for node in arch.nodes]
    write_keel_file(path, arch)
    return arch


def delete_node(root: Path, node_id: str) -> ArchitectureFile:
    """Delete a node and its edges from an architecture diagram.

    Removes the node and all edges where the node is either the
    source or target.

    Args:
        root: Repository root path.
        node_id: ID of the node to delete.

    Returns:
        The updated ArchitectureFile (without the deleted node).

    Raises:
        NodeNotFoundError: If no node with that ID exists.

    Example:
        >>> arch = delete_node(Path("."), "node_deprecated-service")
    """
    path, arch, _ = find_node_location(root, node_id)
    arch.nodes = [node for node in arch.nodes if node.id != node_id]
    arch.edges = [
        edge
        for edge in arch.edges
        if edge.source_id != node_id and edge.target_id != node_id
    ]
    write_keel_file(path, arch)
    return arch


def slugify_node_id(name: str) -> str:
    """Generate a node ID from a human-readable name.

    Converts the name to lowercase, replaces non-alphanumeric characters
    with hyphens, and adds the ``node_`` prefix.

    Args:
        name: Human-readable name (e.g., "API Gateway").

    Returns:
        Node ID suitable for use in architecture files.

    Example:
        >>> slugify_node_id("API Gateway")
        "node_api-gateway"
        >>> slugify_node_id("User Service (v2)")
        "node_user-service-v2"
    """
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"node_{slug or 'new-node'}"

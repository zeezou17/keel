"""Read/write helpers for `.keel/architecture/` files."""

from __future__ import annotations

import re
from pathlib import Path

from keel.file_io import read_keel_file, write_keel_file
from keel.schema import ArchitectureFile, KeelEdge, KeelNode, NodeLevel

ARCHITECTURE_DIR = Path(".keel") / "architecture"


class ArchitectureNotFoundError(FileNotFoundError):
    """Raised when an architecture file cannot be located."""


class NodeNotFoundError(KeyError):
    """Raised when a node id is not present in any architecture file."""


# -- Path resolution (C1/C2/C3 file names on disk) ---------------------------


def architecture_dir(root: Path) -> Path:
    return root / ARCHITECTURE_DIR


def container_slug(container_id: str) -> str:
    return container_id.removeprefix("node_")


def architecture_path(root: Path, level: int, container_id: str | None = None) -> Path:
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
    path = architecture_path(root, level, container_id)
    if not path.exists():
        raise ArchitectureNotFoundError(f"Architecture file not found: {path}")
    return read_keel_file(path, ArchitectureFile)


def save_architecture(path: Path, model: ArchitectureFile) -> None:
    write_keel_file(path, model)


def list_architecture_files(root: Path) -> list[Path]:
    arch_dir = architecture_dir(root)
    if not arch_dir.exists():
        return []
    return sorted(arch_dir.glob("*.json"))


# -- Node lookup and CRUD (used by API and sparring actions) -----------------


def find_node_location(
    root: Path,
    node_id: str,
) -> tuple[Path, ArchitectureFile, KeelNode]:
    for path in list_architecture_files(root):
        arch = read_keel_file(path, ArchitectureFile)
        for node in arch.nodes:
            if node.id == node_id:
                return path, arch, node
    raise NodeNotFoundError(node_id)


def add_node(root: Path, level: int, node: KeelNode, container_id: str | None = None) -> ArchitectureFile:
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
    path, arch, _ = find_node_location(root, node_id)
    arch.nodes = [updates if node.id == node_id else node for node in arch.nodes]
    write_keel_file(path, arch)
    return arch


def delete_node(root: Path, node_id: str) -> ArchitectureFile:
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
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"node_{slug or 'new-node'}"

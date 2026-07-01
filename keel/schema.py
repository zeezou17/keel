"""Pydantic models for every file type Keel reads and writes under ``.keel/``.

These classes are the single source of truth for JSON/YAML/Markdown structure.
The frontend uses matching TypeScript interfaces in ``frontend/src/api/client.ts``.

This module defines:
    - Enumerations for node types, statuses, and priorities
    - Pydantic models for C4 architecture diagrams (nodes and edges)
    - Pydantic models for requirements, ADRs, and characteristics
    - Pydantic models for work packages

Example:
    Loading an architecture file and accessing nodes::

        from keel.schema import ArchitectureFile, KeelNode
        from keel.file_io import read_keel_file

        arch = read_keel_file(Path(".keel/architecture/c1-context.json"), ArchitectureFile)
        for node in arch.nodes:
            print(f"{node.name}: {node.description}")
"""

from __future__ import annotations

import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Shared ────────────────────────────────────────────────────────────────────


class NodeType(str, Enum):
    """C4 model node types.

    Attributes:
        person: A human user of the system.
        system: A software system (highest level of abstraction).
        container: An application or data store within a system.
        component: A component within a container.
        external: An external system or dependency.
    """

    person = "person"
    system = "system"
    container = "container"
    component = "component"
    external = "external"


class NodeLevel(int, Enum):
    """C4 diagram levels.

    Attributes:
        c1: Context diagram level (systems and people).
        c2: Container diagram level (applications and data stores).
        c3: Component diagram level (internal components).
    """

    c1 = 1
    c2 = 2
    c3 = 3


class ReqStatus(str, Enum):
    """Requirement lifecycle status.

    Attributes:
        draft: Requirement is being written or refined.
        approved: Requirement has been reviewed and approved.
        implemented: Requirement has been implemented in code.
    """

    draft = "draft"
    approved = "approved"
    implemented = "implemented"


class ADRStatus(str, Enum):
    """Architecture Decision Record lifecycle status.

    Attributes:
        proposed: Decision is under discussion.
        accepted: Decision has been accepted and is in effect.
        deprecated: Decision is no longer recommended.
        superseded: Decision has been replaced by another ADR.
    """

    proposed = "proposed"
    accepted = "accepted"
    deprecated = "deprecated"
    superseded = "superseded"


class Priority(str, Enum):
    """Priority levels for quality characteristics.

    Attributes:
        high: Critical priority, must be addressed first.
        medium: Important but not critical.
        low: Nice to have, can be deferred.
    """

    high = "high"
    medium = "medium"
    low = "low"


class WPStatus(str, Enum):
    """Work package lifecycle status.

    Attributes:
        todo: Work has not started.
        in_progress: Work is actively being done.
        blocked: Work is blocked by a dependency or issue.
        done: Work has been completed.
    """

    todo = "todo"
    in_progress = "in_progress"
    blocked = "blocked"
    done = "done"


class FitnessFunctionType(str, Enum):
    """Types of fitness functions for architecture characteristics.

    Attributes:
        test: Automated test that verifies the characteristic.
        lint_rule: Static analysis rule that checks the characteristic.
        manual: Manual verification process.
    """

    test = "test"
    lint_rule = "lint-rule"
    manual = "manual"


# ── Architecture: .keel/architecture/*.json ───────────────────────────────────


class KeelNode(BaseModel):
    """A node in a C4 architecture diagram.

    Represents a person, system, container, component, or external dependency
    in the architecture model. Nodes are stored in JSON files under
    ``.keel/architecture/``.

    Attributes:
        id: Unique identifier for the node (e.g., "node_api-gateway").
        type: The type of node (person, system, container, component, external).
        level: The C4 diagram level this node belongs to.
        name: Human-readable name for the node.
        description: Detailed description of what the node represents.
        paths: File path globs that map source code to this node.
        parent_id: ID of the parent node (for components within containers).
        technology: Technology stack used by this node.
        req_ids: IDs of requirements linked to this node.
        adr_ids: IDs of ADRs linked to this node.
        position_x: X coordinate for diagram layout.
        position_y: Y coordinate for diagram layout.
        created_at: Timestamp when the node was created.
        last_verified_at: Timestamp when the node was last verified against code.
    """

    id: str
    type: NodeType
    level: NodeLevel
    name: str
    description: str
    paths: list[str] = Field(default_factory=list)
    parent_id: Optional[str] = None
    technology: Optional[str] = None
    req_ids: list[str] = Field(default_factory=list)
    adr_ids: list[str] = Field(default_factory=list)
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    last_verified_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)


class KeelEdge(BaseModel):
    """An edge (relationship) between nodes in a C4 diagram.

    Represents a dependency, data flow, or other relationship between
    two architecture nodes.

    Attributes:
        id: Unique identifier for the edge (e.g., "edge_api_to_db").
        type: Type of relationship (e.g., "uses", "calls", "reads").
        source_id: ID of the source node.
        target_id: ID of the target node.
        label: Human-readable description of the relationship.
        technology: Technology or protocol used (e.g., "HTTP", "gRPC").
    """

    id: str
    type: str
    source_id: str
    target_id: str
    label: Optional[str] = None
    technology: Optional[str] = None


class ArchitectureFile(BaseModel):
    """A C4 architecture diagram file.

    Represents a complete architecture diagram at a specific C4 level,
    containing nodes and edges. Stored as JSON under ``.keel/architecture/``.

    Attributes:
        schema_version: Version of the Keel schema (currently 1).
        level: The C4 level of this diagram (1, 2, or 3).
        container_id: For C3 diagrams, the parent container ID.
        nodes: List of nodes in this diagram.
        edges: List of edges connecting nodes.
    """

    schema_version: int = 1
    level: NodeLevel
    container_id: Optional[str] = None
    nodes: list[KeelNode]
    edges: list[KeelEdge]


# ── Requirements: .keel/requirements/REQ-*.md (YAML frontmatter) ──────────────


class Requirement(BaseModel):
    """A software requirement with YAML frontmatter.

    Requirements are stored as Markdown files with YAML frontmatter under
    ``.keel/requirements/REQ-*.md``.

    Attributes:
        id: Unique identifier (e.g., "REQ-001").
        title: Short title for the requirement.
        status: Current lifecycle status.
        linked_node_ids: Architecture nodes affected by this requirement.
        acceptance_criteria: List of testable acceptance criteria.
    """

    id: str
    title: str
    status: ReqStatus = ReqStatus.draft
    linked_node_ids: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)


# ── ADRs: .keel/decisions/ADR-*.md (YAML frontmatter) ────────────────────────


class ADR(BaseModel):
    """An Architecture Decision Record.

    ADRs document significant architecture decisions and their rationale.
    Stored as Markdown files with YAML frontmatter under
    ``.keel/decisions/ADR-*.md``.

    Attributes:
        id: Unique identifier (e.g., "ADR-001").
        title: Short title describing the decision.
        status: Current lifecycle status.
        linked_node_ids: Architecture nodes affected by this decision.
        linked_characteristic_ids: Quality characteristics this decision affects.
    """

    id: str
    title: str
    status: ADRStatus = ADRStatus.proposed
    linked_node_ids: list[str] = Field(default_factory=list)
    linked_characteristic_ids: list[str] = Field(default_factory=list)


# ── Characteristics: .keel/characteristics/CHAR-*.yml ────────────────────────


class FitnessFunction(BaseModel):
    """A fitness function for verifying an architecture characteristic.

    Fitness functions provide automated or manual verification that
    an architecture characteristic is being maintained.

    Attributes:
        type: The type of fitness function (test, lint-rule, manual).
        ref: Reference to the test, rule, or manual process.
    """

    type: FitnessFunctionType
    ref: str


class Characteristic(BaseModel):
    """A quality characteristic (non-functional requirement).

    Characteristics describe system qualities like performance, security,
    or maintainability. Stored as YAML files under
    ``.keel/characteristics/CHAR-*.yml``.

    Attributes:
        id: Unique identifier (e.g., "CHAR-001").
        name: Short name for the characteristic (e.g., "Response Time").
        priority: Priority level (high, medium, low).
        scenario: Quality attribute scenario describing the characteristic.
        fitness_function: Optional automated verification mechanism.
        linked_node_ids: Architecture nodes this characteristic applies to.
    """

    id: str
    name: str
    priority: Priority
    scenario: str
    fitness_function: Optional[FitnessFunction] = None
    linked_node_ids: list[str] = Field(default_factory=list)


# ── Work packages: .keel/specs/WP-*.md (YAML frontmatter) ────────────────────


class WorkPackage(BaseModel):
    """A work package specification for implementation.

    Work packages are AI-agent-ready specifications that combine requirements,
    ADRs, and architecture context into actionable implementation tasks.
    Stored as Markdown files with YAML frontmatter under ``.keel/specs/WP-*.md``.

    Attributes:
        id: Unique identifier (e.g., "WP-001").
        title: Short title describing the work to be done.
        status: Current lifecycle status.
        linked_node_id: The architecture node this work package targets.
        linked_req_ids: Requirements addressed by this work package.
        linked_adr_ids: ADRs that guide this work package.
        acceptance_criteria: Testable criteria for completion.
        dependencies: IDs of other work packages this depends on.
    """

    id: str
    title: str
    status: WPStatus = WPStatus.todo
    linked_node_id: str
    linked_req_ids: list[str] = Field(default_factory=list)
    linked_adr_ids: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)

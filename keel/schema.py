"""
Pydantic models for every file type Keel reads and writes under `.keel/`.

These classes are the single source of truth for JSON/YAML/Markdown structure.
The frontend uses matching TypeScript interfaces in frontend/src/api/client.ts.
"""

from __future__ import annotations

import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Shared ────────────────────────────────────────────────────────────────────


class NodeType(str, Enum):
    person = "person"
    system = "system"
    container = "container"
    component = "component"
    external = "external"


class NodeLevel(int, Enum):
    c1 = 1
    c2 = 2
    c3 = 3


class ReqStatus(str, Enum):
    draft = "draft"
    approved = "approved"
    implemented = "implemented"


class ADRStatus(str, Enum):
    proposed = "proposed"
    accepted = "accepted"
    deprecated = "deprecated"
    superseded = "superseded"


class Priority(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class WPStatus(str, Enum):
    todo = "todo"
    in_progress = "in_progress"
    blocked = "blocked"
    done = "done"


class FitnessFunctionType(str, Enum):
    test = "test"
    lint_rule = "lint-rule"
    manual = "manual"


# ── Architecture: .keel/architecture/*.json ───────────────────────────────────


class KeelNode(BaseModel):
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
    id: str
    type: str
    source_id: str
    target_id: str
    label: Optional[str] = None
    technology: Optional[str] = None


class ArchitectureFile(BaseModel):
    schema_version: int = 1
    level: NodeLevel
    container_id: Optional[str] = None
    nodes: list[KeelNode]
    edges: list[KeelEdge]


# ── Requirements: .keel/requirements/REQ-*.md (YAML frontmatter) ──────────────


class Requirement(BaseModel):
    id: str
    title: str
    status: ReqStatus = ReqStatus.draft
    linked_node_ids: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)


# ── ADRs: .keel/decisions/ADR-*.md (YAML frontmatter) ────────────────────────


class ADR(BaseModel):
    id: str
    title: str
    status: ADRStatus = ADRStatus.proposed
    linked_node_ids: list[str] = Field(default_factory=list)
    linked_characteristic_ids: list[str] = Field(default_factory=list)


# ── Characteristics: .keel/characteristics/CHAR-*.yml ────────────────────────


class FitnessFunction(BaseModel):
    type: FitnessFunctionType
    ref: str


class Characteristic(BaseModel):
    id: str
    name: str
    priority: Priority
    scenario: str
    fitness_function: Optional[FitnessFunction] = None
    linked_node_ids: list[str] = Field(default_factory=list)


# ── Work packages: .keel/specs/WP-*.md (YAML frontmatter) ────────────────────


class WorkPackage(BaseModel):
    id: str
    title: str
    status: WPStatus = WPStatus.todo
    linked_node_id: str
    linked_req_ids: list[str] = Field(default_factory=list)
    linked_adr_ids: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)

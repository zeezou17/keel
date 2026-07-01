"""FastAPI server for Keel dev UI and architecture API.

This module is the HTTP layer between the React frontend and the Python
business logic. Each ``/api/*`` route loads or saves data under ``.keel/`` in the
git repo pointed to by the ``KEEL_REPO_ROOT`` environment variable (set by
``keel dev``). Non-API routes serve the pre-built React bundle from ``keel/static/``.

API Endpoints:
    Architecture:
        - GET/PUT ``/api/architecture/{level}`` - C4 diagram CRUD
        - POST ``/api/architecture/node`` - Create node
        - PUT/DELETE ``/api/architecture/node/{node_id}`` - Update/delete node
        - GET ``/api/nodes`` - List all nodes (flat)

    Requirements:
        - GET/POST ``/api/requirements`` - List/create requirements
        - GET/PUT/DELETE ``/api/requirements/{req_id}`` - Requirement CRUD

    ADRs:
        - GET/POST ``/api/adrs`` - List/create ADRs
        - GET/PUT/DELETE ``/api/adrs/{adr_id}`` - ADR CRUD

    Characteristics:
        - GET/POST ``/api/characteristics`` - List/create characteristics
        - GET/PUT/DELETE ``/api/characteristics/{char_id}`` - Characteristic CRUD

    AI Features:
        - POST ``/api/spar`` - AI sparring chat
        - POST ``/api/assess-impact`` - Requirement impact assessment
        - POST ``/api/generate-work-package`` - Generate work package

    Git:
        - GET ``/api/git/status`` - Check .keel/ dirty status
        - POST ``/api/commit`` - Commit .keel/ changes

Example:
    Starting the server programmatically::

        import uvicorn
        from keel.server import app

        uvicorn.run(app, host="127.0.0.1", port=3141)
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from keel.architecture_store import (
    ArchitectureNotFoundError,
    NodeNotFoundError,
    add_node,
    architecture_path,
    delete_node,
    find_node_location,
    load_architecture,
    save_architecture,
    update_node,
)
from keel.assess import AssessImpactRequest, AssessImpactResponse, assess_impact
from keel.claude_bridge import KeelClaudeError
from keel.document_store import (
    DocumentNotFoundError,
    create_adr,
    create_characteristic,
    create_requirement,
    delete_adr,
    delete_characteristic,
    delete_requirement,
    get_adr,
    get_characteristic,
    get_requirement,
    list_adrs,
    list_characteristics,
    list_requirements,
    save_adr,
    save_characteristic,
    save_requirement,
)
from keel.git_utils import KeelGitError, commit_keel_changes, keel_status, open_repo
from keel.schema import ADR, ADRStatus, ArchitectureFile, Characteristic, FitnessFunction, KeelNode, NodeLevel, NodeType, Priority, Requirement, ReqStatus, WorkPackage
from keel.spar import SparRequest, SparResponse, run_spar
from keel.work_packages import (
    GenerateWorkPackageRequest,
    GeneratedWorkPackage,
    WorkPackageGenerationError,
    generate_work_package,
    list_work_packages,
)

STATIC_DIR = Path(__file__).parent / "static"
KEEL_REPO_ROOT_ENV = "KEEL_REPO_ROOT"


# -- API request/response shapes (JSON bodies from the frontend) -------------


class NodeCreateRequest(BaseModel):
    """Request body for creating a new architecture node.

    Attributes:
        level: C4 diagram level (1, 2, or 3).
        container_id: Parent container ID for C3 component nodes.
        node: The KeelNode to create.
    """

    level: int = Field(ge=1, le=3)
    container_id: str | None = None
    node: KeelNode


class CommitRequest(BaseModel):
    """Request body for committing .keel/ changes.

    Attributes:
        message: Git commit message.
    """

    message: str = "chore: update keel architecture"


class RequirementCreateRequest(BaseModel):
    """Request body for creating a new requirement.

    Attributes:
        title: Short title for the requirement.
        description: Detailed description (markdown body).
        acceptance_criteria: List of testable acceptance criteria.
    """

    title: str = Field(min_length=1)
    description: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)


class RequirementUpdateRequest(BaseModel):
    """Request body for updating an existing requirement.

    Attributes:
        title: Short title for the requirement.
        status: Current lifecycle status.
        linked_node_ids: Architecture nodes affected by this requirement.
        acceptance_criteria: List of testable acceptance criteria.
        body: Markdown body content.
    """

    title: str = Field(min_length=1)
    status: ReqStatus
    linked_node_ids: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    body: str = ""


class ADRCreateRequest(BaseModel):
    """Request body for creating a new ADR.

    Attributes:
        title: Short title describing the decision.
        body: Optional markdown body with context, decision, consequences.
    """

    title: str = Field(min_length=1)
    body: str | None = None


class ADRUpdateRequest(BaseModel):
    """Request body for updating an existing ADR.

    Attributes:
        title: Short title describing the decision.
        status: Current lifecycle status.
        linked_node_ids: Architecture nodes affected by this decision.
        linked_characteristic_ids: Quality characteristics this decision affects.
        body: Markdown body content.
    """

    title: str = Field(min_length=1)
    status: ADRStatus
    linked_node_ids: list[str] = Field(default_factory=list)
    linked_characteristic_ids: list[str] = Field(default_factory=list)
    body: str = ""


class CharacteristicCreateRequest(BaseModel):
    """Request body for creating a new quality characteristic.

    Attributes:
        name: Short name for the characteristic.
        priority: Priority level (high, medium, low).
        scenario: Quality attribute scenario describing the characteristic.
        fitness_function: Optional automated verification mechanism.
        linked_node_ids: Architecture nodes this characteristic applies to.
    """

    name: str = Field(min_length=1)
    priority: Priority
    scenario: str = Field(min_length=1)
    fitness_function: FitnessFunction | None = None
    linked_node_ids: list[str] = Field(default_factory=list)


class RequirementResponse(BaseModel):
    """Response body for requirement endpoints.

    Attributes:
        id: Unique identifier.
        title: Short title.
        status: Current lifecycle status.
        linked_node_ids: Linked architecture nodes.
        acceptance_criteria: List of acceptance criteria.
        body: Markdown body content.
    """

    id: str
    title: str
    status: ReqStatus
    linked_node_ids: list[str]
    acceptance_criteria: list[str]
    body: str


class ADRResponse(BaseModel):
    """Response body for ADR endpoints.

    Attributes:
        id: Unique identifier.
        title: Short title.
        status: Current lifecycle status.
        linked_node_ids: Linked architecture nodes.
        linked_characteristic_ids: Linked quality characteristics.
        body: Markdown body content.
    """

    id: str
    title: str
    status: ADRStatus
    linked_node_ids: list[str]
    linked_characteristic_ids: list[str]
    body: str


# -- Small helpers -----------------------------------------------------------


def _requirement_response(requirement: Requirement, body: str) -> RequirementResponse:
    """Convert a Requirement model and body to a RequirementResponse.

    Args:
        requirement: The Requirement model from storage.
        body: The markdown body content.

    Returns:
        A RequirementResponse suitable for JSON serialization.
    """
    return RequirementResponse(
        id=requirement.id,
        title=requirement.title,
        status=requirement.status,
        linked_node_ids=requirement.linked_node_ids,
        acceptance_criteria=requirement.acceptance_criteria,
        body=body,
    )


def _adr_response(adr: ADR, body: str) -> ADRResponse:
    """Convert an ADR model and body to an ADRResponse.

    Args:
        adr: The ADR model from storage.
        body: The markdown body content.

    Returns:
        An ADRResponse suitable for JSON serialization.
    """
    return ADRResponse(
        id=adr.id,
        title=adr.title,
        status=adr.status,
        linked_node_ids=adr.linked_node_ids,
        linked_characteristic_ids=adr.linked_characteristic_ids,
        body=body,
    )


def get_repo_root() -> Path:
    """Get the repository root path from environment or current directory.

    Checks the ``KEEL_REPO_ROOT`` environment variable first, falling back
    to the current working directory if not set.

    Returns:
        Resolved Path to the repository root.
    """
    configured = os.environ.get(KEEL_REPO_ROOT_ENV)
    if configured:
        return Path(configured).resolve()
    return Path.cwd().resolve()


def create_app() -> FastAPI:
    """Create and configure the Keel FastAPI application.

    Sets up all API routes for architecture management, requirements, ADRs,
    characteristics, AI features, and git integration. Also mounts static
    files for the React frontend.

    Returns:
        Configured FastAPI application instance.

    Example:
        >>> from keel.server import create_app
        >>> app = create_app()
        >>> # Use with uvicorn or TestClient
    """
    app = FastAPI(title="Keel", version="0.1.0")

    # -- C4 architecture diagram (nodes, edges, levels) ------------------------

    @app.get("/api/architecture/{level}")
    def get_architecture(
        level: int,
        container_id: str | None = Query(default=None),
    ) -> ArchitectureFile:
        """Get a C4 architecture diagram by level.

        Args:
            level: C4 diagram level (1, 2, or 3).
            container_id: Required for level 3, the parent container ID.

        Returns:
            The ArchitectureFile for the requested level.

        Raises:
            HTTPException: 404 if architecture file not found (except C3).
        """
        root = get_repo_root()
        try:
            return load_architecture(root, level, container_id)
        except ArchitectureNotFoundError as exc:
            if level == 3:
                return ArchitectureFile(
                    level=NodeLevel.c3,
                    container_id=container_id,
                    nodes=[],
                    edges=[],
                )
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.put("/api/architecture/{level}")
    def put_architecture(
        level: int,
        body: ArchitectureFile,
        container_id: str | None = Query(default=None),
    ) -> ArchitectureFile:
        """Update a C4 architecture diagram.

        Args:
            level: C4 diagram level (1, 2, or 3).
            body: The updated ArchitectureFile.
            container_id: Required for level 3, the parent container ID.

        Returns:
            The saved ArchitectureFile.

        Raises:
            HTTPException: 400 if body level doesn't match path level.
        """
        root = get_repo_root()
        if body.level.value != level:
            raise HTTPException(status_code=400, detail="Body level does not match path level.")

        path = architecture_path(root, level, container_id or body.container_id)
        save_architecture(path, body)
        return body

    @app.post("/api/architecture/node")
    def create_node(request: NodeCreateRequest) -> ArchitectureFile:
        """Create a new architecture node.

        Args:
            request: NodeCreateRequest with level, container_id, and node.

        Returns:
            The updated ArchitectureFile containing the new node.

        Raises:
            HTTPException: 400 if node ID already exists.
        """
        root = get_repo_root()
        try:
            return add_node(root, request.level, request.node, request.container_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/architecture/node/{node_id}")
    def put_node(node_id: str, node: KeelNode) -> ArchitectureFile:
        """Update an existing architecture node.

        Args:
            node_id: The node ID to update.
            node: The updated KeelNode (id must match path).

        Returns:
            The updated ArchitectureFile.

        Raises:
            HTTPException: 400 if body id doesn't match path, 404 if not found.
        """
        root = get_repo_root()
        if node.id != node_id:
            raise HTTPException(status_code=400, detail="Node id in body must match path.")
        try:
            return update_node(root, node_id, node)
        except NodeNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.delete("/api/architecture/node/{node_id}")
    def remove_node(node_id: str) -> ArchitectureFile:
        """Delete an architecture node and its edges.

        Args:
            node_id: The node ID to delete.

        Returns:
            The updated ArchitectureFile without the deleted node.

        Raises:
            HTTPException: 404 if node not found.
        """
        root = get_repo_root()
        try:
            return delete_node(root, node_id)
        except NodeNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    # -- Git integration (dirty flag and commit from the toolbar) --------------

    @app.get("/api/git/status")
    def git_status() -> dict[str, object]:
        """Get git status for the .keel/ directory.

        Returns:
            Dict with 'dirty' boolean and 'changed_files' list.

        Raises:
            HTTPException: 400 if not in a git repository.
        """
        root = get_repo_root()
        try:
            repo = open_repo(root)
        except KeelGitError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return keel_status(repo)

    @app.post("/api/commit")
    def commit_changes(request: CommitRequest) -> dict[str, str]:
        """Commit all .keel/ changes.

        Args:
            request: CommitRequest with commit message.

        Returns:
            Dict with 'commit' containing the new commit SHA.

        Raises:
            HTTPException: 400 if no changes or git error.
        """
        root = get_repo_root()
        try:
            repo = open_repo(root)
            commit_sha = commit_keel_changes(repo, request.message)
        except KeelGitError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"commit": commit_sha}

    # -- AI sparring chat (Claude Code architecture assistant) -----------------

    @app.post("/api/spar")
    def spar(request: SparRequest) -> SparResponse:
        """Run an AI sparring conversation about architecture.

        Args:
            request: SparRequest with message, level, and optional history.

        Returns:
            SparResponse with reply text and optional node actions.

        Raises:
            HTTPException: 502 if Claude CLI fails.
        """
        root = get_repo_root()
        try:
            return run_spar(root, request)
        except KeelClaudeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    # -- Flat node list (used when linking requirements to diagram nodes) ------

    @app.get("/api/nodes")
    def list_nodes() -> list[KeelNode]:
        """List all architecture nodes from C1 and C2 diagrams.

        Returns:
            Flat list of all KeelNode objects.
        """
        root = get_repo_root()
        nodes: list[KeelNode] = []
        for level in (1, 2):
            path = architecture_path(root, level)
            if path.exists():
                arch = load_architecture(root, level)
                nodes.extend(arch.nodes)
        return nodes

    # -- Requirements (.keel/requirements/*.md) ---------------------------------

    @app.get("/api/requirements")
    def get_requirements() -> list[RequirementResponse]:
        """List all requirements.

        Returns:
            List of RequirementResponse objects with body content.
        """
        root = get_repo_root()
        return [_requirement_response(req, body) for req, body in list_requirements(root)]

    @app.get("/api/requirements/{req_id}")
    def get_requirement_by_id(req_id: str) -> RequirementResponse:
        """Get a single requirement by ID.

        Args:
            req_id: The requirement ID (e.g., "REQ-001").

        Returns:
            RequirementResponse with body content.

        Raises:
            HTTPException: 404 if requirement not found.
        """
        root = get_repo_root()
        try:
            req, body = get_requirement(root, req_id)
        except DocumentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _requirement_response(req, body)

    @app.post("/api/requirements")
    def post_requirement(request: RequirementCreateRequest) -> RequirementResponse:
        """Create a new requirement.

        Args:
            request: RequirementCreateRequest with title and description.

        Returns:
            RequirementResponse for the created requirement.
        """
        root = get_repo_root()
        req, body = create_requirement(
            root,
            title=request.title,
            description=request.description,
            acceptance_criteria=request.acceptance_criteria,
        )
        return _requirement_response(req, body)

    @app.put("/api/requirements/{req_id}")
    def put_requirement(req_id: str, request: RequirementUpdateRequest) -> RequirementResponse:
        """Update an existing requirement.

        Args:
            req_id: The requirement ID to update.
            request: RequirementUpdateRequest with updated fields.

        Returns:
            RequirementResponse for the updated requirement.

        Raises:
            HTTPException: 404 if requirement not found.
        """
        root = get_repo_root()
        try:
            existing, _ = get_requirement(root, req_id)
        except DocumentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        updated = Requirement(
            id=existing.id,
            title=request.title,
            status=request.status,
            linked_node_ids=request.linked_node_ids,
            acceptance_criteria=request.acceptance_criteria,
        )
        try:
            save_requirement(root, updated, request.body)
        except DocumentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _requirement_response(updated, request.body)

    @app.delete("/api/requirements/{req_id}")
    def remove_requirement(req_id: str) -> dict[str, str]:
        """Delete a requirement.

        Args:
            req_id: The requirement ID to delete.

        Returns:
            Dict with 'deleted' containing the deleted ID.

        Raises:
            HTTPException: 404 if requirement not found.
        """
        root = get_repo_root()
        try:
            delete_requirement(root, req_id)
        except DocumentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"deleted": req_id}

    # -- Architecture Decision Records (.keel/decisions/*.md) ------------------

    @app.get("/api/adrs")
    def get_adrs() -> list[ADRResponse]:
        """List all ADRs.

        Returns:
            List of ADRResponse objects with body content.
        """
        root = get_repo_root()
        return [_adr_response(adr, body) for adr, body in list_adrs(root)]

    @app.get("/api/adrs/{adr_id}")
    def get_adr_by_id(adr_id: str) -> ADRResponse:
        """Get a single ADR by ID.

        Args:
            adr_id: The ADR ID (e.g., "ADR-001").

        Returns:
            ADRResponse with body content.

        Raises:
            HTTPException: 404 if ADR not found.
        """
        root = get_repo_root()
        try:
            adr, body = get_adr(root, adr_id)
        except DocumentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _adr_response(adr, body)

    @app.post("/api/adrs")
    def post_adr(request: ADRCreateRequest) -> ADRResponse:
        """Create a new ADR.

        Args:
            request: ADRCreateRequest with title and optional body.

        Returns:
            ADRResponse for the created ADR.
        """
        root = get_repo_root()
        adr, body = create_adr(root, title=request.title, body=request.body)
        return _adr_response(adr, body)

    @app.put("/api/adrs/{adr_id}")
    def put_adr(adr_id: str, request: ADRUpdateRequest) -> ADRResponse:
        """Update an existing ADR.

        Args:
            adr_id: The ADR ID to update.
            request: ADRUpdateRequest with updated fields.

        Returns:
            ADRResponse for the updated ADR.

        Raises:
            HTTPException: 404 if ADR not found.
        """
        root = get_repo_root()
        try:
            existing, _ = get_adr(root, adr_id)
        except DocumentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        updated = ADR(
            id=existing.id,
            title=request.title,
            status=request.status,
            linked_node_ids=request.linked_node_ids,
            linked_characteristic_ids=request.linked_characteristic_ids,
        )
        try:
            save_adr(root, updated, request.body)
        except DocumentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _adr_response(updated, request.body)

    @app.delete("/api/adrs/{adr_id}")
    def remove_adr(adr_id: str) -> dict[str, str]:
        """Delete an ADR.

        Args:
            adr_id: The ADR ID to delete.

        Returns:
            Dict with 'deleted' containing the deleted ID.

        Raises:
            HTTPException: 404 if ADR not found.
        """
        root = get_repo_root()
        try:
            delete_adr(root, adr_id)
        except DocumentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"deleted": adr_id}

    # -- Quality characteristics (.keel/characteristics/*.yml) -----------------

    @app.get("/api/characteristics")
    def get_characteristics() -> list[Characteristic]:
        """List all quality characteristics.

        Returns:
            List of Characteristic objects.
        """
        root = get_repo_root()
        return list_characteristics(root)

    @app.get("/api/characteristics/{char_id}")
    def get_characteristic_by_id(char_id: str) -> Characteristic:
        """Get a single characteristic by ID.

        Args:
            char_id: The characteristic ID (e.g., "CHAR-001").

        Returns:
            The Characteristic object.

        Raises:
            HTTPException: 404 if characteristic not found.
        """
        root = get_repo_root()
        try:
            return get_characteristic(root, char_id)
        except DocumentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/characteristics")
    def post_characteristic(request: CharacteristicCreateRequest) -> Characteristic:
        """Create a new quality characteristic.

        Args:
            request: CharacteristicCreateRequest with name, priority, scenario.

        Returns:
            The created Characteristic object.
        """
        root = get_repo_root()
        characteristic = Characteristic(
            id="",
            name=request.name,
            priority=request.priority,
            scenario=request.scenario,
            fitness_function=request.fitness_function,
            linked_node_ids=request.linked_node_ids,
        )
        return create_characteristic(root, characteristic)

    @app.put("/api/characteristics/{char_id}")
    def put_characteristic(char_id: str, characteristic: Characteristic) -> Characteristic:
        """Update an existing characteristic.

        Args:
            char_id: The characteristic ID to update.
            characteristic: The updated Characteristic (id must match path).

        Returns:
            The updated Characteristic object.

        Raises:
            HTTPException: 400 if body id doesn't match path, 404 if not found.
        """
        root = get_repo_root()
        if characteristic.id != char_id:
            raise HTTPException(status_code=400, detail="Characteristic id in body must match path.")
        try:
            return save_characteristic(root, characteristic)
        except DocumentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.delete("/api/characteristics/{char_id}")
    def remove_characteristic(char_id: str) -> dict[str, str]:
        """Delete a characteristic.

        Args:
            char_id: The characteristic ID to delete.

        Returns:
            Dict with 'deleted' containing the deleted ID.

        Raises:
            HTTPException: 404 if characteristic not found.
        """
        root = get_repo_root()
        try:
            delete_characteristic(root, char_id)
        except DocumentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"deleted": char_id}

    # -- AI impact assessment and work package generation ----------------------

    @app.post("/api/assess-impact")
    def post_assess_impact(request: AssessImpactRequest) -> AssessImpactResponse:
        """Assess architecture impact of a requirement using AI.

        Args:
            request: AssessImpactRequest with requirement_id.

        Returns:
            AssessImpactResponse with list of impacted nodes.

        Raises:
            HTTPException: 404 if requirement not found, 502 if Claude fails.
        """
        root = get_repo_root()
        try:
            return assess_impact(root, request.requirement_id)
        except DocumentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except KeelClaudeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/api/work-packages")
    def get_work_packages() -> list[dict[str, object]]:
        """List all work packages.

        Returns:
            List of dicts with 'work_package' and 'body' keys.
        """
        root = get_repo_root()
        return [
            {
                "work_package": wp.model_dump(mode="json"),
                "body": body,
            }
            for wp, body in list_work_packages(root)
        ]

    @app.post("/api/generate-work-package")
    def post_generate_work_package(request: GenerateWorkPackageRequest) -> GeneratedWorkPackage:
        """Generate a work package for an architecture node using AI.

        Args:
            request: GenerateWorkPackageRequest with node_id and requirement_ids.

        Returns:
            GeneratedWorkPackage with the created work package and path.

        Raises:
            HTTPException: 400 if node has no requirements, 502 if Claude fails.
        """
        root = get_repo_root()
        try:
            return generate_work_package(root, request)
        except WorkPackageGenerationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeelClaudeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    # -- Static React UI (built by scripts/build_frontend.sh) --------------------

    @app.get("/")
    def index() -> FileResponse:
        """Serve the React frontend index.html.

        Returns:
            FileResponse with the index.html file.

        Raises:
            HTTPException: 503 if frontend bundle is missing.
        """
        index_path = STATIC_DIR / "index.html"
        if not index_path.exists():
            raise HTTPException(
                status_code=503,
                detail="Frontend bundle missing. Run scripts/build_frontend.sh.",
            )
        return FileResponse(index_path)

    if STATIC_DIR.exists():
        app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    return app


app = create_app()

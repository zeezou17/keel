# FP-004 — UML and multi-viewpoint diagrams

**Status:** Backlog (research needed)  
**Priority:** Later  
**Depends on:** WP-001, WP-004, [FP-003](planned-selective-drill-down.md) (recommended)  
**Related:** WP-005 (sparring), WP-008 (drift)

## Problem

Keel is built around **C4-style structural architecture** today:

- C1 context, C2 containers, C3 components (C4 code level not yet modeled)
- One node/edge schema tuned to `person`, `system`, `container`, `component`, `external`
- Canvas and AI prompts assume C4 vocabulary

That is strong for **system structure and boundaries**, but many teams also need **UML and related viewpoints** for design detail — especially inside a container or component:

| Viewpoint | Typical notation | What it answers |
|-----------|------------------|-----------------|
| Structure (shipped) | C4 | What are the major systems and containers? |
| Design / static structure | UML class, component, package | What classes, interfaces, and modules exist? |
| Behavior | UML sequence, activity, state | How do interactions and lifecycles work? |
| Deployment | UML deployment | Where do artifacts run? |
| API / contracts | (often custom or OpenAPI-linked) | What do services expose? |

Without these, Keel cannot yet be the single “living architecture” surface for implementation-level design — users export mentally to other tools (PlantUML, Mermaid, draw.io, IDE diagrams).

## Vision (draft)

Extend Keel beyond C4-only canvases so users can **generate, view, and maintain additional diagram types** — starting with UML — while keeping `.keel/` as the git-backed source of truth.

Rough direction (subject to research):

```
C1 System
  └─ C2 Container
       ├─ C4/C3 components (today)
       └─ Linked viewpoints (new)
            ├─ UML class diagram
            ├─ UML sequence diagram
            └─ …
```

Diagrams should **link back to C4 nodes** (e.g. a class diagram scoped to `API Container`, a sequence diagram for a use case touching two containers) so requirements, drift, and sparring stay coherent.

## Open research (before implementation)

These decisions need exploration — treat this section as the active backlog:

### 1. Which notations first?

| Candidate | Pros | Questions |
|-----------|------|-----------|
| **UML class** | Familiar; maps to code structure | Store as JSON nodes or import from source? |
| **UML sequence** | Great for behavior / ADR discussions | Textual (PlantUML/Mermaid) vs graphical editor? |
| **UML component / deployment** | Overlaps with C2/C4 | Redundant with C4 or complementary? |
| **C4 code level (C4)** | Natural extension of current model | Same schema as C3 or new level? |
| **ArchiMate, BPMN, ER** | Enterprise / process coverage | Too broad for v1? |

**Action:** Pick 1–2 pilot notations (likely **class + sequence**) and document mapping rules to C4.

### 2. Storage model

Options to evaluate:

| Approach | Description |
|----------|-------------|
| **A. Per-viewpoint JSON files** | e.g. `.keel/diagrams/{container-id}/class.json` — mirrors current architecture files |
| **B. Embedded in node metadata** | Diagram ref on container node; payload in separate file |
| **C. Text DSL in `.keel/`** | PlantUML/Mermaid source files; render in UI |
| **D. Generated-only** | AI emits diagram text; no structured edit until later |

Keel’s existing atomic JSON + Pydantic pattern (WP-001) favors **A** or **B**, but sequence diagrams may be easier as **C** initially.

### 3. Relationship to C4 nodes

- **Scoped diagrams** — one UML class diagram per container or component node
- **Cross-cutting diagrams** — sequence across containers; need multi-parent linking
- **Drift** — do class diagrams drift-check against `paths` globs / AST, or stay documentation-only at first?
- **Sparring** — separate prompt templates per notation vs one “viewpoint-aware” prompt

### 4. Canvas / editor UX

- Separate tab per viewpoint (“Structure | Class | Sequence”) vs layers on one canvas
- Reuse React Flow for class-like graphs; sequence may need a different renderer
- [FP-003](planned-selective-drill-down.md) expand-in-place may be the right shell for opening UML under a container

### 5. AI generation

- `keel init` — stay C4-only or optional UML bootstrap?
- Sparring — “generate class diagram for this container” as a new action type
- Validation — UML has its own rules (naming, associations, lifelines); need notation-specific validators like today’s C4 semantic checks

## Proposed phases (tentative)

### Phase 0 — Research (current)

- [ ] Survey target users: which UML diagrams they actually maintain
- [ ] Compare C4 code level vs UML component/class for Keel’s audience
- [ ] Spike: store + render one PlantUML or Mermaid sequence diagram from `.keel/`
- [ ] Spike: class diagram as React Flow graph linked to a container node
- [ ] Write decision record (ADR) for storage format and first notation

### Phase 1 — First viewpoint (TBD after research)

- [ ] Schema + file layout for chosen notation
- [ ] API routes mirroring architecture CRUD pattern
- [ ] Canvas or read-only renderer in `keel dev`
- [ ] Link diagram to parent C4 node

### Phase 2 — AI-assisted generation

- [ ] Sparring / work-package actions to generate or update viewpoint diagrams
- [ ] Validation + retry loop (same pattern as init / spar)

### Phase 3 — Additional notations

- [ ] Second UML type or C4 level-4 code diagram
- [ ] Cross-diagram navigation from requirements and drift reports

## Acceptance criteria

Deferred until Phase 0 research completes. Initial research milestone:

- [ ] ADR published in `.keel/` or `features/` choosing first notation, storage format, and C4 linking model
- [ ] One documented example repo layout under `.keel/diagrams/` (or equivalent)

## Out of scope (until researched)

- Full UML 2.x compliance certification
- Bidirectional sync with external tools (Lucidchart, Enterprise Architect)
- Real-time collaborative editing
- Replacing C4 as Keel’s primary structural model

## References (starting points)

- [C4 model](https://c4model.com/) — current Keel baseline
- [UML 2.5 specification](https://www.omg.org/spec/UML/) — notation reference
- [Structurizr views](https://docs.structurizr.com/) — multi-viewpoint inspiration (C4 + supplements)
- [PlantUML](https://plantuml.com/) / [Mermaid](https://mermaid.js.org/) — text DSL render options

## Notes

This feature is intentionally **backlog-only**. No schema or API changes should land until Phase 0 produces an ADR. Revisit priority after [FP-003](planned-selective-drill-down.md) — expand-in-place navigation is likely the right entry point for opening UML viewpoints under a container.

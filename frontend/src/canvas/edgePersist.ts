/**
 * Resolve which architecture file should own a manually drawn edge.
 */
import type { ArchitectureFile, KeelEdge } from "../api/client";
import type { ComposedNode, ExpansionState } from "./expansion";
import { getCachedArchitecture } from "./expansion";

export interface EdgePersistRequest {
  level: number;
  architecture: ArchitectureFile;
  containerId?: string | null;
  edge: KeelEdge;
}

export type EdgePersistResult =
  | { ok: true; request: EdgePersistRequest }
  | { ok: false; error: string };

function findComposedNode(
  nodeId: string,
  composedNodes: ComposedNode[] | undefined,
): ComposedNode | undefined {
  return composedNodes?.find((node) => node.id === nodeId);
}

function edgeExists(architecture: ArchitectureFile, sourceId: string, targetId: string): boolean {
  return architecture.edges.some(
    (edge) => edge.source_id === sourceId && edge.target_id === targetId,
  );
}

function makeEdgeId(sourceId: string, targetId: string): string {
  const stamp = Date.now().toString(36);
  return `edge_${sourceId}_${targetId}_${stamp}`;
}

/** Build the architecture update for a new canvas edge. */
export function buildEdgePersistRequest(
  sourceId: string,
  targetId: string,
  label: string,
  c1Architecture: ArchitectureFile,
  c2Architecture: ArchitectureFile | null,
  expansionState: ExpansionState,
  composedNodes?: ComposedNode[],
  fullLevelArchitecture?: ArchitectureFile | null,
): EdgePersistResult {
  if (sourceId === targetId) {
    return { ok: false, error: "Cannot link a node to itself." };
  }

  const trimmedLabel = label.trim();
  if (!trimmedLabel) {
    return { ok: false, error: "Relationship label is required." };
  }

  if (fullLevelArchitecture) {
    const source = fullLevelArchitecture.nodes.find((node) => node.id === sourceId);
    const target = fullLevelArchitecture.nodes.find((node) => node.id === targetId);
    if (!source || !target) {
      return { ok: false, error: "Both nodes must exist on the current diagram." };
    }
    if (edgeExists(fullLevelArchitecture, sourceId, targetId)) {
      return { ok: false, error: "A link between these nodes already exists." };
    }
    const edge: KeelEdge = {
      id: makeEdgeId(sourceId, targetId),
      type: "dependency",
      source_id: sourceId,
      target_id: targetId,
      label: trimmedLabel,
    };
    return {
      ok: true,
      request: {
        level: fullLevelArchitecture.level,
        containerId: fullLevelArchitecture.container_id ?? null,
        architecture: { ...fullLevelArchitecture, edges: [...fullLevelArchitecture.edges, edge] },
        edge,
      },
    };
  }

  const source = findComposedNode(sourceId, composedNodes);
  const target = findComposedNode(targetId, composedNodes);
  if (!source || !target) {
    return { ok: false, error: "Both nodes must be visible on the canvas." };
  }

  if (source.depth !== target.depth) {
    return { ok: false, error: "Links must connect nodes at the same C4 level." };
  }

  const depth = source.depth;
  const edge: KeelEdge = {
    id: makeEdgeId(sourceId, targetId),
    type: "dependency",
    source_id: sourceId,
    target_id: targetId,
    label: trimmedLabel,
  };

  if (depth === 1) {
    if (edgeExists(c1Architecture, sourceId, targetId)) {
      return { ok: false, error: "A link between these nodes already exists." };
    }
    return {
      ok: true,
      request: {
        level: 1,
        architecture: { ...c1Architecture, edges: [...c1Architecture.edges, edge] },
        edge,
      },
    };
  }

  if (depth === 2) {
    if (!c2Architecture) {
      return { ok: false, error: "C2 architecture is not loaded." };
    }
    if (edgeExists(c2Architecture, sourceId, targetId)) {
      return { ok: false, error: "A link between these nodes already exists." };
    }
    return {
      ok: true,
      request: {
        level: 2,
        architecture: { ...c2Architecture, edges: [...c2Architecture.edges, edge] },
        edge,
      },
    };
  }

  const containerId = source.parentGroupId ?? target.parentGroupId;
  if (!containerId || source.parentGroupId !== target.parentGroupId) {
    return { ok: false, error: "C3 links must connect components in the same container." };
  }

  const c3Architecture = getCachedArchitecture(expansionState, containerId);
  if (!c3Architecture) {
    return { ok: false, error: "Component architecture is not loaded." };
  }
  if (edgeExists(c3Architecture, sourceId, targetId)) {
    return { ok: false, error: "A link between these nodes already exists." };
  }

  return {
    ok: true,
    request: {
      level: 3,
      containerId,
      architecture: { ...c3Architecture, edges: [...c3Architecture.edges, edge] },
      edge,
    },
  };
}

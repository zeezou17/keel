/**
 * Persist React Flow node positions back to the correct architecture files.
 */
import type { Node } from "@xyflow/react";

import type { ArchitectureFile } from "../api/client";
import type { ExpansionState } from "./expansion";
import { getCachedArchitecture } from "./expansion";

export interface PositionPersistRequest {
  level: number;
  architecture: ArchitectureFile;
  containerId?: string | null;
}

function isFlowNode(node: Node): boolean {
  return !node.id.startsWith("group-");
}

function applyPositions(
  architecture: ArchitectureFile,
  positions: Map<string, { x: number; y: number }>,
): ArchitectureFile | null {
  let changed = false;
  const nodes = architecture.nodes.map((node) => {
    const pos = positions.get(node.id);
    if (!pos) return node;
    if (node.position_x === pos.x && node.position_y === pos.y) return node;
    changed = true;
    return { ...node, position_x: pos.x, position_y: pos.y };
  });
  return changed ? { ...architecture, nodes } : null;
}

/** Map dragged flow nodes to architecture file updates by C-level. */
export function buildPositionPersistRequests(
  flowNodes: Node[],
  c1Architecture: ArchitectureFile,
  c2Architecture: ArchitectureFile | null,
  expansionState: ExpansionState,
): PositionPersistRequest[] {
  const requests: PositionPersistRequest[] = [];
  const c1Positions = new Map<string, { x: number; y: number }>();
  const c2Positions = new Map<string, { x: number; y: number }>();
  const c3PositionsByContainer = new Map<string, Map<string, { x: number; y: number }>>();

  for (const flowNode of flowNodes) {
    if (!isFlowNode(flowNode)) continue;

    const raw = (flowNode.data as { raw?: { id: string; level: number } }).raw;
    if (!raw) continue;

    const pos = { x: flowNode.position.x, y: flowNode.position.y };
    const parentGroupId = (flowNode.data as { parentGroupId?: string }).parentGroupId;

    if (raw.level === 1 && !parentGroupId) {
      c1Positions.set(raw.id, pos);
    } else if (raw.level === 2) {
      c2Positions.set(raw.id, pos);
    } else if (raw.level === 3 && parentGroupId) {
      let bucket = c3PositionsByContainer.get(parentGroupId);
      if (!bucket) {
        bucket = new Map();
        c3PositionsByContainer.set(parentGroupId, bucket);
      }
      bucket.set(raw.id, pos);
    }
  }

  const c1Updated = applyPositions(c1Architecture, c1Positions);
  if (c1Updated) {
    requests.push({ level: 1, architecture: c1Updated });
  }

  if (c2Architecture && c2Positions.size > 0) {
    const c2Updated = applyPositions(c2Architecture, c2Positions);
    if (c2Updated) {
      requests.push({ level: 2, architecture: c2Updated });
    }
  }

  for (const [containerId, positions] of c3PositionsByContainer) {
    const cached = getCachedArchitecture(expansionState, containerId);
    if (!cached) continue;
    const c3Updated = applyPositions(cached, positions);
    if (c3Updated) {
      requests.push({ level: 3, architecture: c3Updated, containerId });
    }
  }

  return requests;
}

/**
 * When an expanded parent is dragged, move its visible children by the same delta.
 */
import type { Node, NodeChange } from "@xyflow/react";
import { applyNodeChanges } from "@xyflow/react";

export function applyNodeChangesWithChildFollow(
  changes: NodeChange[],
  nodes: Node[],
  expandedIds: Set<string>,
): Node[] {
  let next = applyNodeChanges(changes, nodes);

  for (const change of changes) {
    if (change.type !== "position" || !change.position) continue;
    if (!expandedIds.has(change.id)) continue;

    const previous = nodes.find((node) => node.id === change.id);
    const current = next.find((node) => node.id === change.id);
    if (!previous || !current) continue;

    const dx = current.position.x - previous.position.x;
    const dy = current.position.y - previous.position.y;
    if (dx === 0 && dy === 0) continue;

    next = next.map((node) => {
      const parentGroupId = (node.data as { parentGroupId?: string }).parentGroupId;
      if (parentGroupId !== change.id || node.id.startsWith("group-")) {
        return node;
      }
      return {
        ...node,
        position: {
          x: node.position.x + dx,
          y: node.position.y + dy,
        },
      };
    });
  }

  return next;
}

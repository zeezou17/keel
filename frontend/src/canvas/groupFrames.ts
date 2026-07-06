/**
 * Synthetic React Flow group frames for expanded C4 nodes.
 *
 * Frames are always derived from live canvas positions, never arch-file coords.
 */
import type { Node } from "@xyflow/react";

import { calculateGroupFrame } from "./layout";

export const GROUP_COLORS: Record<number, { border: string; background: string }> = {
  1: { border: "#2a9d8f", background: "rgba(42, 157, 143, 0.08)" },
  2: { border: "#457b9d", background: "rgba(69, 123, 157, 0.08)" },
};

/** Strip group/header nodes, then rebuild frames for currently expanded parents. */
export function rebuildGroupFrames(allNodes: Node[], expandedIds: Set<string>): Node[] {
  const withoutGroups = allNodes.filter((n) => !n.id.startsWith("group-"));
  const result: Node[] = [...withoutGroups];

  for (const parentNode of withoutGroups) {
    if (!expandedIds.has(parentNode.id)) continue;

    const children = withoutGroups.filter((n) => {
      const data = n.data as { parentGroupId?: string };
      return data.parentGroupId === parentNode.id;
    });

    if (children.length === 0) continue;

    const depth = (parentNode.data as { depth?: number }).depth ?? 1;
    const colors = GROUP_COLORS[depth] ?? GROUP_COLORS[1];
    const frame = calculateGroupFrame(parentNode, children);
    const name = (parentNode.data as { label?: string }).label ?? parentNode.id;

    result.push({
      id: `group-${parentNode.id}`,
      type: "default",
      position: frame.position,
      data: { label: "" },
      style: {
        width: frame.width,
        height: frame.height,
        border: `2px dashed ${colors.border}`,
        borderRadius: 12,
        background: colors.background,
        zIndex: 0,
        pointerEvents: "none" as const,
      },
      selectable: false,
      draggable: false,
    });

    result.push({
      id: `group-header-${parentNode.id}`,
      type: "default",
      position: { x: frame.position.x, y: frame.position.y - 28 },
      data: {
        label: `${name} · C${depth + 1} · ${children.length} children`,
      },
      style: {
        background: colors.border,
        color: "#ffffff",
        padding: "4px 10px",
        borderRadius: "8px 8px 0 0",
        fontSize: "0.8rem",
        fontWeight: 600,
        border: "none",
        zIndex: 1,
        pointerEvents: "none" as const,
      },
      selectable: false,
      draggable: false,
    });
  }

  return result;
}

/** Merge freshly built nodes with positions already on the canvas. */
export function mergeWithLivePositions(rawNodes: Node[], liveNodes: Node[]): Node[] {
  return rawNodes.map((rawNode) => {
    const existing = liveNodes.find((n) => n.id === rawNode.id);
    if (existing && !rawNode.id.startsWith("group-")) {
      return { ...rawNode, position: existing.position };
    }
    return rawNode;
  });
}

/**
 * Layout utilities for the C4 canvas.
 *
 * Provides smart positioning that respects user-placed nodes while
 * making room for expanded groups.
 */
import type { Node } from "@xyflow/react";

export interface LayoutOptions {
  nodeWidth: number;
  nodeHeight: number;
  groupPadding: number;
  minSpacing: number;
}

const DEFAULT_OPTIONS: LayoutOptions = {
  nodeWidth: 180,
  nodeHeight: 80,
  groupPadding: 40,
  minSpacing: 30,
};

interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * Check if two rectangles overlap.
 */
function rectsOverlap(a: Rect, b: Rect, padding: number = 0): boolean {
  return !(
    a.x + a.width + padding < b.x ||
    b.x + b.width + padding < a.x ||
    a.y + a.height + padding < b.y ||
    b.y + b.height + padding < a.y
  );
}

/**
 * Calculate the bounds of an expanded group including its children.
 */
export function calculateGroupBounds(
  parentNode: Node,
  childNodes: Node[],
  options: Partial<LayoutOptions> = {}
): Rect {
  const opts = { ...DEFAULT_OPTIONS, ...options };

  if (childNodes.length === 0) {
    return {
      x: parentNode.position.x,
      y: parentNode.position.y,
      width: opts.nodeWidth,
      height: opts.nodeHeight,
    };
  }

  // Calculate grid layout for children
  const childCount = childNodes.length;
  const cols = Math.min(3, Math.ceil(Math.sqrt(childCount)));
  const rows = Math.ceil(childCount / cols);

  const groupWidth = cols * opts.nodeWidth + (cols - 1) * opts.minSpacing + opts.groupPadding * 2;
  const groupHeight = rows * opts.nodeHeight + (rows - 1) * opts.minSpacing + opts.groupPadding * 2 + 30;

  // Group starts below the parent node
  const groupX = parentNode.position.x - opts.groupPadding;

  // Total bounds includes parent + group
  return {
    x: Math.min(parentNode.position.x, groupX),
    y: parentNode.position.y,
    width: Math.max(opts.nodeWidth, groupWidth),
    height: opts.nodeHeight + 20 + groupHeight,
  };
}

/**
 * Position children inside an expanded group in a grid layout.
 * Returns new positions for children only.
 * 
 * Children are positioned relative to their parent, below it in a grid.
 */
export function layoutChildrenInGroup(
  parentNode: Node,
  childNodes: Node[],
  options: Partial<LayoutOptions> = {}
): Map<string, { x: number; y: number }> {
  const opts = { ...DEFAULT_OPTIONS, ...options };
  const positions = new Map<string, { x: number; y: number }>();

  if (childNodes.length === 0) {
    return positions;
  }

  const cols = Math.min(3, Math.ceil(Math.sqrt(childNodes.length)));

  // Group starts below the parent
  const groupX = parentNode.position.x;
  const groupStartY = parentNode.position.y + opts.nodeHeight + 50; // 50 = gap + header

  childNodes.forEach((child, index) => {
    const col = index % cols;
    const row = Math.floor(index / cols);

    // Check if child already has a valid position that's near the parent
    // (not at 0,0 and not a default grid position from before)
    const hasPosition = child.position.x !== 0 || child.position.y !== 0;
    const isNearParent = hasPosition && 
      Math.abs(child.position.x - parentNode.position.x) < 800 &&
      child.position.y > parentNode.position.y;

    if (isNearParent) {
      // Keep the existing position - it's a reasonable user placement
      positions.set(child.id, child.position);
    } else {
      // Apply grid layout relative to parent
      positions.set(child.id, {
        x: groupX + col * (opts.nodeWidth + opts.minSpacing),
        y: groupStartY + row * (opts.nodeHeight + opts.minSpacing),
      });
    }
  });

  return positions;
}

/**
 * Push overlapping nodes away from an expanded group.
 * Only moves nodes that actually overlap - preserves other positions.
 * 
 * This is a soft push - nodes return to their original position when collapsed.
 * Users can freely drag nodes after they've been pushed.
 */
export function pushOverlappingNodes(
  allNodes: Node[],
  expandedNodeId: string,
  groupBounds: Rect,
  options: Partial<LayoutOptions> = {}
): Map<string, { x: number; y: number }> {
  const opts = { ...DEFAULT_OPTIONS, ...options };
  const newPositions = new Map<string, { x: number; y: number }>();

  // Find nodes that might need to move (root level, not part of the expanded group)
  const nodesToCheck = allNodes.filter((n) => {
    if (n.id === expandedNodeId) return false;
    if (n.id.startsWith("group-")) return false;
    const parentGroupId = (n.data as { parentGroupId?: string })?.parentGroupId;
    if (parentGroupId === expandedNodeId) return false;
    if (parentGroupId) return false; // Child of another group
    return true;
  });

  for (const node of nodesToCheck) {
    const nodeRect: Rect = {
      x: node.position.x,
      y: node.position.y,
      width: opts.nodeWidth,
      height: opts.nodeHeight,
    };

    if (rectsOverlap(nodeRect, groupBounds, opts.minSpacing)) {
      // Calculate the center of both rects to determine optimal push direction
      const nodeCenterX = node.position.x + opts.nodeWidth / 2;
      const nodeCenterY = node.position.y + opts.nodeHeight / 2;
      const groupCenterX = groupBounds.x + groupBounds.width / 2;
      const groupCenterY = groupBounds.y + groupBounds.height / 2;

      // Calculate distances needed to clear the overlap in each direction
      const clearRight = groupBounds.x + groupBounds.width - node.position.x + opts.minSpacing;
      const clearLeft = node.position.x + opts.nodeWidth - groupBounds.x + opts.minSpacing;
      const clearDown = groupBounds.y + groupBounds.height - node.position.y + opts.minSpacing;
      const clearUp = node.position.y + opts.nodeHeight - groupBounds.y + opts.minSpacing;

      let newX = node.position.x;
      let newY = node.position.y;

      // Push in the direction the node is already positioned relative to group center
      // This maintains the general layout topology
      if (nodeCenterX >= groupCenterX && nodeCenterY >= groupCenterY) {
        // Node is to the right and below - push right or down
        if (clearRight < clearDown) {
          newX = groupBounds.x + groupBounds.width + opts.minSpacing;
        } else {
          newY = groupBounds.y + groupBounds.height + opts.minSpacing;
        }
      } else if (nodeCenterX < groupCenterX && nodeCenterY >= groupCenterY) {
        // Node is to the left and below - push left or down
        if (clearLeft < clearDown) {
          newX = groupBounds.x - opts.nodeWidth - opts.minSpacing;
        } else {
          newY = groupBounds.y + groupBounds.height + opts.minSpacing;
        }
      } else if (nodeCenterX >= groupCenterX && nodeCenterY < groupCenterY) {
        // Node is to the right and above - push right or up
        if (clearRight < clearUp) {
          newX = groupBounds.x + groupBounds.width + opts.minSpacing;
        } else {
          newY = groupBounds.y - opts.nodeHeight - opts.minSpacing;
        }
      } else {
        // Node is to the left and above - push left or up
        if (clearLeft < clearUp) {
          newX = groupBounds.x - opts.nodeWidth - opts.minSpacing;
        } else {
          newY = groupBounds.y - opts.nodeHeight - opts.minSpacing;
        }
      }

      newPositions.set(node.id, { x: newX, y: newY });
    }
  }

  return newPositions;
}

/**
 * Apply initial layout to nodes that don't have positions yet.
 * Preserves existing positions.
 */
export function applyInitialLayout(
  nodes: Node[],
  options: Partial<LayoutOptions> = {}
): Node[] {
  const opts = { ...DEFAULT_OPTIONS, ...options };

  const result: Node[] = [];
  let rootIndex = 0;

  for (const node of nodes) {
    if (node.id.startsWith("group-")) {
      result.push(node);
      continue;
    }

    const hasPosition = node.position.x !== 0 || node.position.y !== 0;

    if (hasPosition) {
      result.push(node);
    } else {
      // Apply default grid position for root nodes without positions
      const parentGroupId = (node.data as { parentGroupId?: string })?.parentGroupId;
      if (!parentGroupId) {
        const col = rootIndex % 4;
        const row = Math.floor(rootIndex / 4);
        result.push({
          ...node,
          position: {
            x: 100 + col * (opts.nodeWidth + 80),
            y: 100 + row * (opts.nodeHeight + 100),
          },
        });
        rootIndex++;
      } else {
        result.push(node);
      }
    }
  }

  return result;
}

/**
 * Calculate group frame position and size based on children.
 */
export function calculateGroupFrame(
  parentNode: Node,
  childNodes: Node[],
  options: Partial<LayoutOptions> = {}
): { position: { x: number; y: number }; width: number; height: number } {
  const opts = { ...DEFAULT_OPTIONS, ...options };

  if (childNodes.length === 0) {
    return {
      position: { x: parentNode.position.x, y: parentNode.position.y + opts.nodeHeight + 20 },
      width: opts.nodeWidth + opts.groupPadding * 2,
      height: 100,
    };
  }

  // Find bounds of all children
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

  for (const child of childNodes) {
    minX = Math.min(minX, child.position.x);
    minY = Math.min(minY, child.position.y);
    maxX = Math.max(maxX, child.position.x + opts.nodeWidth);
    maxY = Math.max(maxY, child.position.y + opts.nodeHeight);
  }

  const padding = 20;

  return {
    position: {
      x: minX - padding,
      y: minY - padding - 28, // Account for header
    },
    width: maxX - minX + padding * 2,
    height: maxY - minY + padding * 2,
  };
}

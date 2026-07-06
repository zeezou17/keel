/**
 * Auto-layout engine for the C4 canvas using dagre.
 *
 * Automatically positions nodes when the graph structure changes (expand/collapse),
 * pushing sibling nodes to make room for expanded groups.
 */
import dagre from "dagre";
import type { Node, Edge } from "@xyflow/react";

export interface LayoutOptions {
  direction: "TB" | "LR" | "BT" | "RL";
  nodeWidth: number;
  nodeHeight: number;
  nodeSeparation: number;
  rankSeparation: number;
  groupPadding: number;
}

const DEFAULT_OPTIONS: LayoutOptions = {
  direction: "TB",
  nodeWidth: 180,
  nodeHeight: 80,
  nodeSeparation: 50,
  rankSeparation: 100,
  groupPadding: 40,
};

/**
 * Apply dagre layout to a set of nodes and edges.
 * Returns new nodes with updated positions.
 */
export function applyDagreLayout(
  nodes: Node[],
  edges: Edge[],
  options: Partial<LayoutOptions> = {}
): Node[] {
  const opts = { ...DEFAULT_OPTIONS, ...options };

  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({
    rankdir: opts.direction,
    nodesep: opts.nodeSeparation,
    ranksep: opts.rankSeparation,
    marginx: 20,
    marginy: 20,
  });

  // Add nodes to dagre graph
  for (const node of nodes) {
    // Skip group frame nodes - they'll be positioned based on their children
    if (node.id.startsWith("group-")) continue;

    dagreGraph.setNode(node.id, {
      width: opts.nodeWidth,
      height: opts.nodeHeight,
    });
  }

  // Add edges to dagre graph
  for (const edge of edges) {
    // Only add edges between nodes that exist in the graph
    if (dagreGraph.hasNode(edge.source) && dagreGraph.hasNode(edge.target)) {
      dagreGraph.setEdge(edge.source, edge.target);
    }
  }

  // Run the layout algorithm
  dagre.layout(dagreGraph);

  // Apply calculated positions to nodes
  return nodes.map((node) => {
    // Skip group nodes - handle them separately
    if (node.id.startsWith("group-")) {
      return node;
    }

    const dagreNode = dagreGraph.node(node.id);
    if (!dagreNode) {
      return node;
    }

    return {
      ...node,
      position: {
        x: dagreNode.x - opts.nodeWidth / 2,
        y: dagreNode.y - opts.nodeHeight / 2,
      },
    };
  });
}

/**
 * Layout nodes with hierarchical grouping support.
 *
 * This handles the case where expanded nodes have children that should be
 * grouped together, and sibling nodes should be pushed to make room.
 */
export function applyHierarchicalLayout(
  nodes: Node[],
  edges: Edge[],
  expandedNodeIds: Set<string>,
  options: Partial<LayoutOptions> = {}
): Node[] {
  const opts = { ...DEFAULT_OPTIONS, ...options };

  // Separate nodes by their parent group
  const rootNodes = nodes.filter(
    (n) => !n.id.startsWith("group-") && !n.parentId && !getParentGroupId(n)
  );
  const childNodesByParent = new Map<string, Node[]>();

  for (const node of nodes) {
    if (node.id.startsWith("group-")) continue;
    const parentId = getParentGroupId(node);
    if (parentId) {
      if (!childNodesByParent.has(parentId)) {
        childNodesByParent.set(parentId, []);
      }
      childNodesByParent.get(parentId)!.push(node);
    }
  }

  // Calculate the size each expanded group needs
  const groupSizes = new Map<string, { width: number; height: number }>();

  for (const [parentId, children] of childNodesByParent) {
    if (children.length === 0) continue;

    // Layout children internally
    const childCount = children.length;
    const cols = Math.ceil(Math.sqrt(childCount));
    const rows = Math.ceil(childCount / cols);

    const width =
      cols * opts.nodeWidth + (cols - 1) * opts.nodeSeparation + opts.groupPadding * 2;
    const height =
      rows * opts.nodeHeight + (rows - 1) * (opts.rankSeparation / 2) + opts.groupPadding * 2 + 30; // +30 for header

    groupSizes.set(parentId, { width, height });
  }

  // Create a dagre graph for root-level layout
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({
    rankdir: opts.direction,
    nodesep: opts.nodeSeparation,
    ranksep: opts.rankSeparation,
    marginx: 40,
    marginy: 40,
  });

  // Add root nodes with their sizes (expanded nodes are larger)
  for (const node of rootNodes) {
    const isExpanded = expandedNodeIds.has(node.id);
    const groupSize = groupSizes.get(node.id);

    let width = opts.nodeWidth;
    let height = opts.nodeHeight;

    if (isExpanded && groupSize) {
      // The expanded node needs room for itself + its children group
      width = Math.max(opts.nodeWidth, groupSize.width);
      height = opts.nodeHeight + groupSize.height + 20; // gap between node and group
    }

    dagreGraph.setNode(node.id, { width, height });
  }

  // Add root-level edges
  const rootNodeIds = new Set(rootNodes.map((n) => n.id));
  for (const edge of edges) {
    if (rootNodeIds.has(edge.source) && rootNodeIds.has(edge.target)) {
      dagreGraph.setEdge(edge.source, edge.target);
    }
  }

  // Run layout for root level
  dagre.layout(dagreGraph);

  // Build the final positioned nodes
  const positionedNodes: Node[] = [];

  for (const node of rootNodes) {
    const dagreNode = dagreGraph.node(node.id);
    if (!dagreNode) {
      positionedNodes.push(node);
      continue;
    }

    const isExpanded = expandedNodeIds.has(node.id);
    const groupSize = groupSizes.get(node.id);

    // Position the root node at the top of its allocated space
    const nodeX = dagreNode.x - opts.nodeWidth / 2;
    const nodeY = isExpanded && groupSize
      ? dagreNode.y - dagreNode.height / 2
      : dagreNode.y - opts.nodeHeight / 2;

    positionedNodes.push({
      ...node,
      position: { x: nodeX, y: nodeY },
    });

    // Position children if expanded
    if (isExpanded && groupSize) {
      const children = childNodesByParent.get(node.id) ?? [];
      const groupX = dagreNode.x - groupSize.width / 2;
      const groupY = nodeY + opts.nodeHeight + 20;

      // Add group frame node
      const groupFrameNode = nodes.find((n) => n.id === `group-${node.id}`);
      if (groupFrameNode) {
        positionedNodes.push({
          ...groupFrameNode,
          position: { x: groupX, y: groupY },
          style: {
            ...groupFrameNode.style,
            width: groupSize.width,
            height: groupSize.height - 30,
          },
        });
      }

      // Add group header node
      const groupHeaderNode = nodes.find((n) => n.id === `group-header-${node.id}`);
      if (groupHeaderNode) {
        positionedNodes.push({
          ...groupHeaderNode,
          position: { x: groupX, y: groupY - 28 },
        });
      }

      // Layout children in a grid inside the group
      const cols = Math.ceil(Math.sqrt(children.length));
      children.forEach((child, index) => {
        const col = index % cols;
        const row = Math.floor(index / cols);

        const childX = groupX + opts.groupPadding + col * (opts.nodeWidth + opts.nodeSeparation);
        const childY = groupY + opts.groupPadding + row * (opts.nodeHeight + opts.rankSeparation / 2);

        // Check if this child is also expanded (nested expansion)
        const childIsExpanded = expandedNodeIds.has(child.id);
        const childGroupSize = groupSizes.get(child.id);

        positionedNodes.push({
          ...child,
          position: { x: childX, y: childY },
        });

        // Handle nested children (C3 inside C2)
        if (childIsExpanded && childGroupSize) {
          const nestedChildren = childNodesByParent.get(child.id) ?? [];
          const nestedGroupX = childX;
          const nestedGroupY = childY + opts.nodeHeight + 15;

          // Add nested group frame
          const nestedGroupFrame = nodes.find((n) => n.id === `group-${child.id}`);
          if (nestedGroupFrame) {
            positionedNodes.push({
              ...nestedGroupFrame,
              position: { x: nestedGroupX, y: nestedGroupY },
              style: {
                ...nestedGroupFrame.style,
                width: childGroupSize.width,
                height: childGroupSize.height - 30,
              },
            });
          }

          // Add nested group header
          const nestedGroupHeader = nodes.find((n) => n.id === `group-header-${child.id}`);
          if (nestedGroupHeader) {
            positionedNodes.push({
              ...nestedGroupHeader,
              position: { x: nestedGroupX, y: nestedGroupY - 28 },
            });
          }

          // Layout nested children
          const nestedCols = Math.ceil(Math.sqrt(nestedChildren.length));
          nestedChildren.forEach((nested, nestedIndex) => {
            const nestedCol = nestedIndex % nestedCols;
            const nestedRow = Math.floor(nestedIndex / nestedCols);

            positionedNodes.push({
              ...nested,
              position: {
                x: nestedGroupX + opts.groupPadding + nestedCol * (opts.nodeWidth + opts.nodeSeparation),
                y: nestedGroupY + opts.groupPadding + nestedRow * (opts.nodeHeight + opts.rankSeparation / 2),
              },
            });
          });
        }
      });
    }
  }

  // Add any remaining group nodes that weren't processed
  for (const node of nodes) {
    if (node.id.startsWith("group-") && !positionedNodes.find((n) => n.id === node.id)) {
      positionedNodes.push(node);
    }
  }

  return positionedNodes;
}

/**
 * Extract parent group ID from node data.
 */
function getParentGroupId(node: Node): string | null {
  const data = node.data as { parentGroupId?: string | null };
  return data?.parentGroupId ?? null;
}

/**
 * Animate transition between two sets of node positions.
 * Returns a function to update positions over time.
 */
export function createLayoutTransition(
  fromNodes: Node[],
  toNodes: Node[],
  _duration: number = 300
): (progress: number) => Node[] {
  const fromPositions = new Map(fromNodes.map((n) => [n.id, n.position]));

  return (progress: number) => {
    const eased = easeInOutCubic(progress);

    return toNodes.map((toNode) => {
      const fromPos = fromPositions.get(toNode.id);
      if (!fromPos) {
        return toNode;
      }

      return {
        ...toNode,
        position: {
          x: fromPos.x + (toNode.position.x - fromPos.x) * eased,
          y: fromPos.y + (toNode.position.y - fromPos.y) * eased,
        },
      };
    });
  };
}

function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

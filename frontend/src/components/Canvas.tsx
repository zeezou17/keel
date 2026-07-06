/**
 * Interactive C4 diagram in the center panel.
 *
 * Uses React Flow to render nodes/edges with selective drill-down (FP-003).
 * Supports expand-in-place via chevron controls on system/container nodes.
 * 
 * Layout behavior:
 * - Users can freely drag and position any node
 * - When expanding, only overlapping nodes are pushed out of the way
 * - Child nodes are laid out in a grid inside the group
 * - Positions are preserved and saved
 */
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Node,
  type NodeChange,
  type Edge,
  applyNodeChanges,
  useReactFlow,
  ReactFlowProvider,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { ArchitectureFile, KeelNode } from "../api/client";
import type { ComposedNode, ExpansionState } from "../canvas/expansion";
import { canNodeExpand } from "../canvas/expansion";
import {
  applyInitialLayout,
  layoutChildrenInGroup,
  calculateGroupFrame,
  calculateGroupBounds,
  pushOverlappingNodes,
} from "../canvas/layout";
import { ExpandableNode, type ExpandableNodeData } from "./ExpandableNode";

const GROUP_COLORS: Record<number, { border: string; background: string }> = {
  1: { border: "#2a9d8f", background: "rgba(42, 157, 143, 0.08)" },
  2: { border: "#457b9d", background: "rgba(69, 123, 157, 0.08)" },
};

const nodeTypes = {
  expandable: ExpandableNode,
};

interface CanvasProps {
  architecture: ArchitectureFile;
  composedNodes?: ComposedNode[];
  expansionState?: ExpansionState;
  highlightedNodeIds?: string[];
  selectedNodeId?: string | null;
  onArchitectureChange: (architecture: ArchitectureFile, level: number, containerId?: string | null) => void;
  onNodeSelect?: (node: KeelNode | null) => void;
  onNodeExpand?: (node: KeelNode) => void;
  onNodeCollapse?: (node: KeelNode) => void;
  onNodeDoubleClick?: (node: KeelNode) => void;
}

function CanvasInner({
  architecture,
  composedNodes,
  expansionState,
  highlightedNodeIds = [],
  selectedNodeId = null,
  onArchitectureChange,
  onNodeSelect,
  onNodeExpand,
  onNodeCollapse,
  onNodeDoubleClick,
}: CanvasProps) {
  const { fitView } = useReactFlow();
  const highlightSet = useMemo(() => new Set(highlightedNodeIds), [highlightedNodeIds]);
  const previousExpansionRef = useRef<Set<string>>(new Set());
  const [nodes, setNodes] = useState<Node[]>([]);
  const [isInitialized, setIsInitialized] = useState(false);

  const isEmphasized = useCallback(
    (nodeId: string) => highlightSet.has(nodeId) || nodeId === selectedNodeId,
    [highlightSet, selectedNodeId],
  );

  // Build React Flow nodes from architecture data
  const buildNodes = useCallback((): Node[] => {
    if (composedNodes && expansionState) {
      return buildComposedNodes(composedNodes, expansionState, isEmphasized);
    }
    return buildSimpleNodes(architecture.nodes, isEmphasized);
  }, [composedNodes, expansionState, architecture.nodes, isEmphasized]);

  function buildSimpleNodes(archNodes: KeelNode[], checkEmphasized: (id: string) => boolean): Node[] {
    return archNodes.map((node) => {
      const hasChildren = canNodeExpand(node);
      const isExpanded = expansionState?.expandedNodeIds.has(node.id) ?? false;
      const emphasized = checkEmphasized(node.id);

      // Use saved position or default to 0,0 (will be laid out)
      const position = {
        x: node.position_x ?? 0,
        y: node.position_y ?? 0,
      };

      return {
        id: node.id,
        type: "expandable",
        position,
        data: {
          label: node.name,
          nodeType: node.type,
          description: node.description,
          depth: node.level,
          isExpanded,
          hasChildren,
          isHighlighted: emphasized,
          isSelected: node.id === selectedNodeId,
          parentGroupId: null,
          raw: node,
          onExpand: hasChildren ? () => onNodeExpand?.(node) : undefined,
          onCollapse: isExpanded ? () => onNodeCollapse?.(node) : undefined,
        } satisfies ExpandableNodeData & { raw: KeelNode; parentGroupId: string | null },
        style: { zIndex: 10 },
      };
    });
  }

  function buildComposedNodes(
    composed: ComposedNode[],
    _state: ExpansionState,
    checkEmphasized: (id: string) => boolean
  ): Node[] {
    const result: Node[] = [];

    // Get the set of expanded node IDs for quick lookup
    const expandedIds = expansionState?.expandedNodeIds ?? new Set<string>();

    // Build a set of valid parent IDs (nodes that exist in the composed list)
    const validParentIds = new Set(composed.map((n) => n.id));

    // Build regular nodes first (using saved positions)
    for (const node of composed) {
      // Skip children whose parent is NOT expanded
      // This prevents stray children from appearing after refresh
      if (node.parentGroupId) {
        // First check if parent exists in the current view
        if (!validParentIds.has(node.parentGroupId)) {
          continue; // Parent doesn't exist, skip this orphan
        }
        // Then check if parent is expanded
        const parentExpanded = expandedIds.has(node.parentGroupId);
        if (!parentExpanded) {
          continue; // Don't render this child
        }
      }

      const emphasized = checkEmphasized(node.id);

      result.push({
        id: node.id,
        type: "expandable",
        position: {
          x: node.position_x ?? 0,
          y: node.position_y ?? 0,
        },
        data: {
          label: node.name,
          nodeType: node.type,
          description: node.description,
          depth: node.depth,
          isExpanded: node.isExpanded,
          hasChildren: node.hasChildren,
          isHighlighted: emphasized,
          isSelected: node.id === selectedNodeId,
          parentGroupId: node.parentGroupId,
          raw: node,
          onExpand: node.hasChildren && !node.isExpanded ? () => onNodeExpand?.(node) : undefined,
          onCollapse: node.isExpanded ? () => onNodeCollapse?.(node) : undefined,
        } satisfies ExpandableNodeData & { raw: KeelNode; parentGroupId: string | null | undefined },
        style: { zIndex: 10 + node.depth },
      });
    }

    // Add group frames for expanded nodes that have visible children
    for (const node of composed) {
      // Only add group if this node is actually expanded AND in the expanded set
      if (!node.isExpanded || !expandedIds.has(node.id)) {
        continue;
      }

      const children = result.filter((n) => {
        const data = n.data as { parentGroupId?: string };
        return data.parentGroupId === node.id;
      });

      // Only add group frame if there are visible children
      if (children.length > 0) {
        const parentNode = result.find((n) => n.id === node.id);
        if (parentNode) {
          const colors = GROUP_COLORS[node.depth] ?? GROUP_COLORS[1];
          const frame = calculateGroupFrame(parentNode, children);

          result.push({
            id: `group-${node.id}`,
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
            id: `group-header-${node.id}`,
            type: "default",
            position: { x: frame.position.x, y: frame.position.y - 28 },
            data: {
              label: `${node.name} · C${node.depth + 1} · ${children.length} children`,
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
      }
    }

    return result;
  }

  const buildEdges = useCallback((): Edge[] => {
    return architecture.edges.map((edge) => ({
      id: edge.id,
      source: edge.source_id,
      target: edge.target_id,
      label: edge.label ?? edge.type,
      style: { zIndex: 5 },
    }));
  }, [architecture.edges]);

  const edges = useMemo(() => buildEdges(), [buildEdges]);

  // Initialize nodes and handle expansion changes
  useEffect(() => {
    const rawNodes = buildNodes();
    const currentExpanded = expansionState?.expandedNodeIds ?? new Set();
    const previousExpanded = previousExpansionRef.current;

    // Check what changed
    const newlyExpanded = [...currentExpanded].filter((id) => !previousExpanded.has(id));
    const newlyCollapsed = [...previousExpanded].filter((id) => !currentExpanded.has(id));
    const expansionChanged = newlyExpanded.length > 0 || newlyCollapsed.length > 0;

    if (!isInitialized) {
      // First render - apply initial layout to nodes without positions
      const layoutedNodes = applyInitialLayout(rawNodes);
      setNodes(layoutedNodes);
      setIsInitialized(true);
      previousExpansionRef.current = new Set(currentExpanded);

      // Fit view after initial render
      setTimeout(() => fitView({ padding: 0.2 }), 100);
      return;
    }

    if (expansionChanged) {
      // Handle expansion change
      let updatedNodes = [...rawNodes];

      // For newly expanded nodes, layout children and push overlapping siblings
      for (const expandedId of newlyExpanded) {
        const parentNode = updatedNodes.find((n) => n.id === expandedId);
        if (!parentNode) continue;

        // Find children of this node
        const childNodes = updatedNodes.filter((n) => {
          const data = n.data as { parentGroupId?: string };
          return data.parentGroupId === expandedId;
        });

        if (childNodes.length > 0) {
          // Layout children in grid
          const childPositions = layoutChildrenInGroup(parentNode, childNodes);
          updatedNodes = updatedNodes.map((n) => {
            const newPos = childPositions.get(n.id);
            return newPos ? { ...n, position: newPos } : n;
          });

          // Calculate group bounds and push overlapping nodes
          const groupBounds = calculateGroupBounds(parentNode, childNodes);
          const pushPositions = pushOverlappingNodes(updatedNodes, expandedId, groupBounds);
          updatedNodes = updatedNodes.map((n) => {
            const newPos = pushPositions.get(n.id);
            return newPos ? { ...n, position: newPos } : n;
          });
        }
      }

      // Update group frames based on new positions
      updatedNodes = updateGroupFrames(updatedNodes, currentExpanded);

      // Animate to new positions
      animateToPositions(nodes, updatedNodes, () => {
        setNodes(updatedNodes);
        setTimeout(() => fitView({ padding: 0.2, duration: 200 }), 50);
      });

      previousExpansionRef.current = new Set(currentExpanded);
    } else {
      // No expansion change - just update node data (e.g., highlights)
      setNodes((current) => {
        return rawNodes.map((rawNode) => {
          const existingNode = current.find((n) => n.id === rawNode.id);
          if (existingNode && !rawNode.id.startsWith("group-")) {
            // Keep existing position, update data
            return { ...rawNode, position: existingNode.position };
          }
          return rawNode;
        });
      });
    }
  }, [buildNodes, expansionState?.expandedNodeIds, isInitialized, fitView]);

  // Animation helper
  const animateToPositions = (
    fromNodes: Node[],
    toNodes: Node[],
    onComplete: () => void
  ) => {
    const duration = 250;
    const startTime = performance.now();
    const fromPositions = new Map(fromNodes.map((n) => [n.id, n.position]));

    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = easeOutCubic(progress);

      const interpolatedNodes = toNodes.map((toNode) => {
        const fromPos = fromPositions.get(toNode.id);
        if (!fromPos) return toNode;

        return {
          ...toNode,
          position: {
            x: fromPos.x + (toNode.position.x - fromPos.x) * eased,
            y: fromPos.y + (toNode.position.y - fromPos.y) * eased,
          },
        };
      });

      setNodes(interpolatedNodes);

      if (progress < 1) {
        requestAnimationFrame(animate);
      } else {
        onComplete();
      }
    };

    requestAnimationFrame(animate);
  };

  // Update group frame positions based on child positions
  function updateGroupFrames(allNodes: Node[], expandedIds: Set<string>): Node[] {
    return allNodes.map((node) => {
      if (!node.id.startsWith("group-") || node.id.startsWith("group-header-")) {
        return node;
      }

      const parentId = node.id.replace("group-", "");
      if (!expandedIds.has(parentId)) return node;

      const parentNode = allNodes.find((n) => n.id === parentId);
      const childNodes = allNodes.filter((n) => {
        const data = n.data as { parentGroupId?: string };
        return data.parentGroupId === parentId;
      });

      if (parentNode && childNodes.length > 0) {
        const frame = calculateGroupFrame(parentNode, childNodes);
        return {
          ...node,
          position: frame.position,
          style: { ...node.style, width: frame.width, height: frame.height },
        };
      }

      return node;
    }).map((node) => {
      // Update header positions
      if (!node.id.startsWith("group-header-")) return node;

      const parentId = node.id.replace("group-header-", "");
      const groupFrame = allNodes.find((n) => n.id === `group-${parentId}`);

      if (groupFrame) {
        return {
          ...node,
          position: { x: groupFrame.position.x, y: groupFrame.position.y - 28 },
        };
      }

      return node;
    });
  }

  const persistPositions = useCallback(
    (nextNodes: Node[]) => {
      const updated: ArchitectureFile = {
        ...architecture,
        nodes: architecture.nodes.map((node) => {
          const flowNode = nextNodes.find((item) => item.id === node.id);
          if (!flowNode) return node;
          return {
            ...node,
            position_x: flowNode.position.x,
            position_y: flowNode.position.y,
          };
        }),
      };
      onArchitectureChange(updated, architecture.level, architecture.container_id);
    },
    [architecture, onArchitectureChange],
  );

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      setNodes((current) => {
        const next = applyNodeChanges(changes, current);

        // Check if a drag finished
        const finishedDrag = changes.some(
          (change) => change.type === "position" && change.dragging === false,
        );

        if (finishedDrag) {
          // Update group frames to follow their children
          const expandedIds = expansionState?.expandedNodeIds ?? new Set();
          const withUpdatedFrames = updateGroupFrames(next, expandedIds);
          persistPositions(withUpdatedFrames);
          return withUpdatedFrames;
        }

        // During drag, update group frames in real-time
        const isDragging = changes.some(
          (change) => change.type === "position" && change.dragging === true,
        );

        if (isDragging) {
          const expandedIds = expansionState?.expandedNodeIds ?? new Set();
          return updateGroupFrames(next, expandedIds);
        }

        return next;
      });
    },
    [persistPositions, expansionState?.expandedNodeIds],
  );

  const onNodeClick = useCallback(
    (_event: React.MouseEvent, flowNode: Node) => {
      if (flowNode.id.startsWith("group-")) return;
      const raw = (flowNode.data as { raw?: KeelNode }).raw;
      if (raw) {
        onNodeSelect?.(raw);
      }
    },
    [onNodeSelect],
  );

  const handleNodeDoubleClick = useCallback(
    (_event: React.MouseEvent, flowNode: Node) => {
      if (flowNode.id.startsWith("group-")) return;
      const raw = (flowNode.data as { raw?: KeelNode }).raw;
      if (raw) {
        if (canNodeExpand(raw)) {
          const isExpanded = expansionState?.expandedNodeIds.has(raw.id);
          if (isExpanded) {
            onNodeCollapse?.(raw);
          } else {
            onNodeExpand?.(raw);
          }
        }
        onNodeDoubleClick?.(raw);
      }
    },
    [expansionState, onNodeExpand, onNodeCollapse, onNodeDoubleClick],
  );

  const onPaneClick = useCallback(() => {
    onNodeSelect?.(null);
  }, [onNodeSelect]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      onNodesChange={onNodesChange}
      onNodeClick={onNodeClick}
      onNodeDoubleClick={handleNodeDoubleClick}
      onPaneClick={onPaneClick}
      fitView
      fitViewOptions={{ padding: 0.2 }}
    >
      <Background />
      <MiniMap />
      <Controls />
    </ReactFlow>
  );
}

function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

export function Canvas(props: CanvasProps) {
  return (
    <div style={{ width: "100%", height: "100%" }}>
      <ReactFlowProvider>
        <CanvasInner {...props} />
      </ReactFlowProvider>
    </div>
  );
}

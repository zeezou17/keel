/**
 * Interactive C4 diagram in the center panel.
 *
 * Uses React Flow to render nodes/edges with selective drill-down (FP-003).
 * Supports expand-in-place via chevron controls on system/container nodes.
 * Auto-layouts nodes using dagre when expansion state changes.
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
import { applyHierarchicalLayout } from "../canvas/layout";
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
  onNodeSelect?: (node: KeelNode) => void;
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
  const isAnimatingRef = useRef(false);

  const isEmphasized = useCallback(
    (nodeId: string) => highlightSet.has(nodeId) || nodeId === selectedNodeId,
    [highlightSet, selectedNodeId],
  );

  // Build React Flow nodes from composed nodes (with expansion) or raw architecture
  const buildNodes = useCallback((): Node[] => {
    if (composedNodes && expansionState) {
      return buildComposedNodes(composedNodes, expansionState, isEmphasized);
    }
    return buildSimpleNodes(architecture.nodes, isEmphasized);
  }, [composedNodes, expansionState, architecture.nodes, isEmphasized]);

  function buildSimpleNodes(nodes: KeelNode[], checkEmphasized: (id: string) => boolean): Node[] {
    return nodes.map((node) => {
      const hasChildren = canNodeExpand(node);
      const isExpanded = expansionState?.expandedNodeIds.has(node.id) ?? false;
      const emphasized = checkEmphasized(node.id);

      return {
        id: node.id,
        type: "expandable",
        position: { x: 0, y: 0 }, // Will be set by layout
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
        style: {
          zIndex: 10,
        },
      };
    });
  }

  function buildComposedNodes(
    composed: ComposedNode[],
    _state: ExpansionState,
    checkEmphasized: (id: string) => boolean
  ): Node[] {
    const result: Node[] = [];

    // First, create group frames for expanded nodes
    for (const node of composed) {
      if (node.isExpanded && node.hasChildren) {
        const children = composed.filter((n) => n.parentGroupId === node.id);
        if (children.length > 0) {
          const colors = GROUP_COLORS[node.depth] ?? GROUP_COLORS[1];

          // Group frame (will be positioned by layout)
          result.push({
            id: `group-${node.id}`,
            type: "default",
            position: { x: 0, y: 0 },
            data: { label: "", parentGroupId: null },
            style: {
              width: 300,
              height: 200,
              border: `2px dashed ${colors.border}`,
              borderRadius: 12,
              background: colors.background,
              zIndex: 0,
              pointerEvents: "none" as const,
            },
            selectable: false,
            draggable: false,
          });

          // Group header
          result.push({
            id: `group-header-${node.id}`,
            type: "default",
            position: { x: 0, y: 0 },
            data: {
              label: `${node.name} · C${node.depth + 1} · ${children.length} children`,
              parentGroupId: null,
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

    // Then create actual nodes
    for (const node of composed) {
      const emphasized = checkEmphasized(node.id);

      result.push({
        id: node.id,
        type: "expandable",
        position: { x: 0, y: 0 }, // Will be set by layout
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
        style: {
          zIndex: 10 + node.depth,
        },
      });
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

  // Build and layout nodes
  const rawNodes = useMemo(() => buildNodes(), [buildNodes]);
  const edges = useMemo(() => buildEdges(), [buildEdges]);

  // Apply layout
  const layoutedNodes = useMemo(() => {
    const expandedIds = expansionState?.expandedNodeIds ?? new Set();
    return applyHierarchicalLayout(rawNodes, edges, expandedIds);
  }, [rawNodes, edges, expansionState?.expandedNodeIds]);

  const [nodes, setNodes] = useState<Node[]>(layoutedNodes);

  // Animate layout changes when expansion state changes
  useEffect(() => {
    const currentExpanded = expansionState?.expandedNodeIds ?? new Set();
    const previousExpanded = previousExpansionRef.current;

    // Check if expansion state actually changed
    const expansionChanged =
      currentExpanded.size !== previousExpanded.size ||
      [...currentExpanded].some((id) => !previousExpanded.has(id)) ||
      [...previousExpanded].some((id) => !currentExpanded.has(id));

    if (expansionChanged && !isAnimatingRef.current) {
      isAnimatingRef.current = true;
      const startNodes = nodes;
      const endNodes = layoutedNodes;
      const duration = 300;
      const startTime = performance.now();

      const animate = (currentTime: number) => {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = easeInOutCubic(progress);

        const interpolatedNodes = endNodes.map((endNode) => {
          const startNode = startNodes.find((n) => n.id === endNode.id);
          if (!startNode) {
            return endNode;
          }

          return {
            ...endNode,
            position: {
              x: startNode.position.x + (endNode.position.x - startNode.position.x) * eased,
              y: startNode.position.y + (endNode.position.y - startNode.position.y) * eased,
            },
          };
        });

        setNodes(interpolatedNodes);

        if (progress < 1) {
          requestAnimationFrame(animate);
        } else {
          isAnimatingRef.current = false;
          // Fit view after animation completes
          setTimeout(() => fitView({ padding: 0.2, duration: 200 }), 50);
        }
      };

      requestAnimationFrame(animate);
      previousExpansionRef.current = new Set(currentExpanded);
    } else if (!expansionChanged) {
      // Just update nodes without animation (e.g., highlight changes)
      setNodes(layoutedNodes);
    }
  }, [layoutedNodes, expansionState?.expandedNodeIds, fitView]);

  // Initial fit view
  useEffect(() => {
    const timer = setTimeout(() => {
      fitView({ padding: 0.2 });
    }, 100);
    return () => clearTimeout(timer);
  }, [fitView]);

  const persistPositions = useCallback(
    (nextNodes: Node[]) => {
      const updated: ArchitectureFile = {
        ...architecture,
        nodes: architecture.nodes.map((node) => {
          const flowNode = nextNodes.find((item) => item.id === node.id);
          if (!flowNode) {
            return node;
          }
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
      // Don't process changes during animation
      if (isAnimatingRef.current) return;

      setNodes((current) => {
        const next = applyNodeChanges(changes, current);
        const finishedDrag = changes.some(
          (change) => change.type === "position" && change.dragging === false,
        );
        if (finishedDrag) {
          persistPositions(next);
        }
        return next;
      });
    },
    [persistPositions],
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
        // Double-click toggles expansion instead of full level switch
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
    onNodeSelect?.(null as unknown as KeelNode);
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

function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
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

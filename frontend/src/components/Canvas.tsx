/**
 * Interactive C4 diagram in the center panel.
 *
 * Uses React Flow to render nodes/edges with selective drill-down (FP-003).
 * Supports expand-in-place via chevron controls on system/container nodes.
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
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { ArchitectureFile, KeelNode } from "../api/client";
import type { ComposedNode, ExpansionState } from "../canvas/expansion";
import { canNodeExpand } from "../canvas/expansion";
import { ExpandableNode, type ExpandableNodeData } from "./ExpandableNode";

const GROUP_COLORS: Record<number, { border: string; background: string }> = {
  1: { border: "#2a9d8f", background: "rgba(42, 157, 143, 0.08)" },
  2: { border: "#457b9d", background: "rgba(69, 123, 157, 0.08)" },
};

function defaultPosition(index: number): { x: number; y: number } {
  const column = index % 5;
  const row = Math.floor(index / 5);
  return { x: 120 + column * 220, y: 100 + row * 140 };
}

function childPosition(index: number, parentX: number, parentY: number): { x: number; y: number } {
  const column = index % 3;
  const row = Math.floor(index / 3);
  return {
    x: parentX + 30 + column * 200,
    y: parentY + 80 + row * 120,
  };
}

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

export function Canvas({
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
  const highlightSet = useMemo(() => new Set(highlightedNodeIds), [highlightedNodeIds]);

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
    return nodes.map((node, index) => {
      const position =
        node.position_x != null && node.position_y != null
          ? { x: node.position_x, y: node.position_y }
          : defaultPosition(index);
      const hasChildren = canNodeExpand(node);
      const isExpanded = expansionState?.expandedNodeIds.has(node.id) ?? false;
      const emphasized = checkEmphasized(node.id);

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
          raw: node,
          onExpand: hasChildren ? () => onNodeExpand?.(node) : undefined,
          onCollapse: isExpanded ? () => onNodeCollapse?.(node) : undefined,
        } satisfies ExpandableNodeData & { raw: KeelNode },
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
    const groupFrames: Map<string, { x: number; y: number; width: number; height: number }> = new Map();

    // First pass: calculate positions for all nodes
    const nodePositions: Map<string, { x: number; y: number }> = new Map();
    let childIndexByParent: Map<string, number> = new Map();

    for (const node of composed) {
      let position: { x: number; y: number };

      if (node.parentGroupId) {
        // Child node - position relative to parent
        const parentNode = composed.find((n) => n.id === node.parentGroupId);
        const parentPos = parentNode
          ? nodePositions.get(parentNode.id) ?? { x: 200, y: 100 }
          : { x: 200, y: 100 };

        const childIndex = childIndexByParent.get(node.parentGroupId) ?? 0;
        childIndexByParent.set(node.parentGroupId, childIndex + 1);

        position =
          node.position_x != null && node.position_y != null
            ? { x: node.position_x, y: node.position_y }
            : childPosition(childIndex, parentPos.x, parentPos.y);
      } else {
        // Root node
        const index = composed.filter((n) => !n.parentGroupId).indexOf(node);
        position =
          node.position_x != null && node.position_y != null
            ? { x: node.position_x, y: node.position_y }
            : defaultPosition(index);
      }

      nodePositions.set(node.id, position);
    }

    // Second pass: calculate group frame bounds
    for (const node of composed) {
      if (node.isExpanded && node.hasChildren) {
        const children = composed.filter((n) => n.parentGroupId === node.id);
        if (children.length > 0) {
          let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

          for (const child of children) {
            const pos = nodePositions.get(child.id)!;
            minX = Math.min(minX, pos.x);
            minY = Math.min(minY, pos.y);
            maxX = Math.max(maxX, pos.x + 180);
            maxY = Math.max(maxY, pos.y + 80);
          }

          const parentPos = nodePositions.get(node.id)!;
          groupFrames.set(node.id, {
            x: Math.min(parentPos.x - 20, minX - 20),
            y: parentPos.y + 60,
            width: Math.max(220, maxX - minX + 60),
            height: Math.max(150, maxY - minY + 80),
          });
        }
      }
    }

    // Third pass: create group frame nodes
    for (const [nodeId, frame] of groupFrames) {
      const parentNode = composed.find((n) => n.id === nodeId);
      if (parentNode) {
        const childCount = composed.filter((n) => n.parentGroupId === nodeId).length;
        const colors = GROUP_COLORS[parentNode.depth] ?? GROUP_COLORS[1];

        result.push({
          id: `group-${nodeId}`,
          type: "default",
          position: { x: frame.x, y: frame.y },
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

        // Group header
        result.push({
          id: `group-header-${nodeId}`,
          type: "default",
          position: { x: frame.x, y: frame.y - 28 },
          data: {
            label: `${parentNode.name} · C${parentNode.depth + 1} · ${childCount} children`,
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

    // Fourth pass: create actual nodes
    for (const node of composed) {
      const position = nodePositions.get(node.id)!;
      const emphasized = checkEmphasized(node.id);

      result.push({
        id: node.id,
        type: "expandable",
        position,
        data: {
          label: node.name,
          nodeType: node.type,
          description: node.description,
          depth: node.depth,
          isExpanded: node.isExpanded,
          hasChildren: node.hasChildren,
          isHighlighted: emphasized,
          isSelected: node.id === selectedNodeId,
          raw: node,
          onExpand: node.hasChildren && !node.isExpanded ? () => onNodeExpand?.(node) : undefined,
          onCollapse: node.isExpanded ? () => onNodeCollapse?.(node) : undefined,
        } satisfies ExpandableNodeData & { raw: KeelNode },
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

  const initialNodes = useMemo(() => buildNodes(), [buildNodes]);
  const [nodes, setNodes] = useState<Node[]>(initialNodes);
  const edges = useMemo(() => buildEdges(), [buildEdges]);

  useEffect(() => {
    setNodes(buildNodes());
  }, [buildNodes]);

  const persistPositions = useCallback(
    (nextNodes: Node[]) => {
      // Only persist position changes for actual architecture nodes (not groups)
      const architectureNodeIds = new Set(architecture.nodes.map((n) => n.id));
      const composedNodeIds = composedNodes ? new Set(composedNodes.map((n) => n.id)) : architectureNodeIds;

      const updatedNodes = nextNodes.filter(
        (n) => !n.id.startsWith("group-") && composedNodeIds.has(n.id)
      );

      // Group nodes by their level for proper persistence
      const nodesByLevel: Map<number, { node: KeelNode; position: { x: number; y: number } }[]> = new Map();

      for (const flowNode of updatedNodes) {
        const rawNode = (flowNode.data as { raw?: KeelNode }).raw;
        if (rawNode) {
          const level = rawNode.level;
          if (!nodesByLevel.has(level)) {
            nodesByLevel.set(level, []);
          }
          nodesByLevel.get(level)!.push({
            node: rawNode,
            position: flowNode.position,
          });
        }
      }

      // For the root architecture, update positions
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
    [architecture, composedNodes, onArchitectureChange],
  );

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
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
    <div style={{ width: "100%", height: "100%" }}>
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
    </div>
  );
}

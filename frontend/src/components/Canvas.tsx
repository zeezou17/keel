/**
 * Interactive C4 diagram in the center panel.
 *
 * Uses React Flow to render nodes/edges from architecture JSON. Dragging a
 * node saves its position back to `.keel/architecture/` via the API.
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

import type { ArchitectureFile, KeelNode, NodeType } from "../api/client";

const NODE_COLORS: Record<NodeType, string> = {
  person: "#f4a261",
  system: "#2a9d8f",
  container: "#457b9d",
  component: "#8d99ae",
  external: "#e76f51",
};

function defaultPosition(index: number): { x: number; y: number } {
  const column = index % 5;
  const row = Math.floor(index / 5);
  return { x: 120 + column * 220, y: 100 + row * 140 };
}

function toFlowNode(node: KeelNode, index: number, highlighted: boolean): Node {
  const position =
    node.position_x != null && node.position_y != null
      ? { x: node.position_x, y: node.position_y }
      : defaultPosition(index);

  return {
    id: node.id,
    position,
    data: {
      label: node.name,
      nodeType: node.type,
      description: node.description,
      raw: node,
    },
    style: {
      border: `3px solid ${highlighted ? "#f9c74f" : NODE_COLORS[node.type]}`,
      borderRadius: 10,
      padding: 10,
      background: highlighted ? "#fff8e6" : "#ffffff",
      width: 180,
      boxShadow: highlighted ? "0 0 0 3px rgba(249, 199, 79, 0.35)" : undefined,
    },
  };
}

function toFlowEdge(edge: ArchitectureFile["edges"][number]): Edge {
  return {
    id: edge.id,
    source: edge.source_id,
    target: edge.target_id,
    label: edge.label ?? edge.type,
  };
}

interface CanvasProps {
  architecture: ArchitectureFile;
  highlightedNodeIds?: string[];
  selectedNodeId?: string | null;
  onArchitectureChange: (architecture: ArchitectureFile) => void;
  onNodeSelect?: (node: KeelNode) => void;
  onNodeOpen?: (node: KeelNode) => void;
}

export function Canvas({
  architecture,
  highlightedNodeIds = [],
  selectedNodeId = null,
  onArchitectureChange,
  onNodeSelect,
  onNodeOpen,
}: CanvasProps) {
  const highlightSet = useMemo(() => new Set(highlightedNodeIds), [highlightedNodeIds]);

  const isEmphasized = useCallback(
    (nodeId: string) => highlightSet.has(nodeId) || nodeId === selectedNodeId,
    [highlightSet, selectedNodeId],
  );

  const initialNodes = useMemo(
    () =>
      architecture.nodes.map((node, index) =>
        toFlowNode(node, index, isEmphasized(node.id)),
      ),
    [architecture, isEmphasized],
  );
  const [nodes, setNodes] = useState<Node[]>(initialNodes);
  const edges = useMemo(() => architecture.edges.map(toFlowEdge), [architecture.edges]);

  useEffect(() => {
    setNodes(
      architecture.nodes.map((node, index) =>
        toFlowNode(node, index, isEmphasized(node.id)),
      ),
    );
  }, [architecture, isEmphasized]);

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
      onArchitectureChange(updated);
    },
    [architecture, onArchitectureChange],
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
      const raw = flowNode.data.raw as KeelNode;
      onNodeSelect?.(raw);
    },
    [onNodeSelect],
  );

  const onNodeDoubleClick = useCallback(
    (_event: React.MouseEvent, flowNode: Node) => {
      const raw = flowNode.data.raw as KeelNode;
      onNodeOpen?.(raw);
    },
    [onNodeOpen],
  );

  return (
    <div style={{ width: "100%", height: "100%" }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onNodeClick={onNodeClick}
        onNodeDoubleClick={onNodeDoubleClick}
        fitView
      >
        <Background />
        <MiniMap />
        <Controls />
      </ReactFlow>
    </div>
  );
}

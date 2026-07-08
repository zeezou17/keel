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
  type Connection,
  type Node,
  type NodeChange,
  type Edge,
  useReactFlow,
  ReactFlowProvider,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { ArchitectureFile, KeelEdge, KeelNode } from "../api/client";
import type { ComposedEdge, ComposedNode, ExpansionState } from "../canvas/expansion";
import { canNodeExpand } from "../canvas/expansion";
import {
  applyInitialLayout,
  layoutChildrenInGroup,
  calculateGroupBounds,
  pushOverlappingNodes,
} from "../canvas/layout";
import { mergeWithLivePositions, rebuildGroupFrames } from "../canvas/groupFrames";
import { applyNodeChangesWithChildFollow } from "../canvas/dragChildren";
import { ExpandableNode, type ExpandableNodeData } from "./ExpandableNode";

const nodeTypes = {
  expandable: ExpandableNode,
};

interface CanvasProps {
  architecture: ArchitectureFile;
  composedNodes?: ComposedNode[];
  composedEdges?: ComposedEdge[];
  expansionState?: ExpansionState;
  highlightedNodeIds?: string[];
  selectedNodeId?: string | null;
  selectedEdgeId?: string | null;
  onArchitectureChange: (architecture: ArchitectureFile, level: number, containerId?: string | null) => void;
  onPersistPositions?: (flowNodes: Node[]) => void;
  onEdgeCreate?: (sourceId: string, targetId: string, label: string) => void;
  onEdgeSelect?: (edge: KeelEdge | null) => void;
  onNodeSelect?: (node: KeelNode | null) => void;
  onNodeExpand?: (node: KeelNode) => void;
  onNodeCollapse?: (node: KeelNode) => void;
  onNodeDoubleClick?: (node: KeelNode) => void;
}

function CanvasInner({
  architecture,
  composedNodes,
  composedEdges,
  expansionState,
  highlightedNodeIds = [],
  selectedNodeId = null,
  selectedEdgeId = null,
  onArchitectureChange,
  onPersistPositions,
  onEdgeCreate,
  onEdgeSelect,
  onNodeSelect,
  onNodeExpand,
  onNodeCollapse,
  onNodeDoubleClick,
}: CanvasProps) {
  const { fitView } = useReactFlow();
  const highlightSet = useMemo(() => new Set(highlightedNodeIds), [highlightedNodeIds]);
  const previousExpansionRef = useRef<Set<string>>(new Set());
  const nodesRef = useRef<Node[]>([]);
  const animationTokenRef = useRef(0);
  const animationFrameRef = useRef<number | null>(null);
  const [nodes, setNodes] = useState<Node[]>([]);
  const [isInitialized, setIsInitialized] = useState(false);

  const cancelAnimation = useCallback(() => {
    if (animationFrameRef.current !== null) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    animationTokenRef.current += 1;
  }, []);

  useEffect(() => () => cancelAnimation(), [cancelAnimation]);

  const isEmphasized = useCallback(
    (nodeId: string) => highlightSet.has(nodeId) || nodeId === selectedNodeId,
    [highlightSet, selectedNodeId],
  );

  nodesRef.current = nodes;

  function mergeFromCanvas(rawNodes: Node[]): Node[] {
    return mergeWithLivePositions(rawNodes, nodesRef.current);
  }

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

    // Group frames are added by rebuildGroupFrames() from live positions,
    // not here — arch-file positions cause stray headers at the origin.

    return result;
  }

  const buildEdges = useCallback((): Edge[] => {
    const mapEdge = (edge: KeelEdge, zIndex: number): Edge => ({
      id: edge.id,
      source: edge.source_id,
      target: edge.target_id,
      label: edge.label ?? edge.type,
      style: {
        zIndex,
        stroke: edge.id === selectedEdgeId ? "#2a9d8f" : undefined,
        strokeWidth: edge.id === selectedEdgeId ? 2.5 : undefined,
      },
      animated: edge.id === selectedEdgeId,
    });

    const rootEdges = architecture.edges.map((edge) => mapEdge(edge, 5));

    if (!composedEdges || !composedNodes || !expansionState) {
      return rootEdges;
    }

    const expandedIds = expansionState.expandedNodeIds;
    const visibleIds = new Set<string>();
    for (const node of composedNodes) {
      if (node.parentGroupId && !expandedIds.has(node.parentGroupId)) {
        continue;
      }
      visibleIds.add(node.id);
    }

    const innerEdges = composedEdges
      .filter((edge) => visibleIds.has(edge.source_id) && visibleIds.has(edge.target_id))
      .map((edge) => mapEdge(edge, edge.depth > 1 ? 6 : 5));

    const byId = new Map<string, Edge>();
    for (const edge of rootEdges) byId.set(edge.id, edge);
    for (const edge of innerEdges) byId.set(edge.id, edge);
    return [...byId.values()];
  }, [architecture.edges, composedEdges, composedNodes, expansionState, selectedEdgeId]);

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
      const layoutedNodes = rebuildGroupFrames(
        applyInitialLayout(rawNodes),
        currentExpanded,
      );
      setNodes(layoutedNodes);
      setIsInitialized(true);
      previousExpansionRef.current = new Set(currentExpanded);

      // Fit view after initial render
      setTimeout(() => fitView({ padding: 0.2 }), 100);
      return;
    }

    if (expansionChanged) {
      cancelAnimation();
      let updatedNodes = mergeFromCanvas(rawNodes);

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

          const laidOutChildren = updatedNodes.filter((n) => {
            const data = n.data as { parentGroupId?: string };
            return data.parentGroupId === expandedId;
          });

          const groupBounds = calculateGroupBounds(parentNode, laidOutChildren);
          const pushPositions = pushOverlappingNodes(updatedNodes, expandedId, groupBounds);
          updatedNodes = updatedNodes.map((n) => {
            const newPos = pushPositions.get(n.id);
            return newPos ? { ...n, position: newPos } : n;
          });
        }
      }

      updatedNodes = rebuildGroupFrames(updatedNodes, currentExpanded);

      if (onPersistPositions) {
        onPersistPositions(updatedNodes);
      }

      // Collapse removes nodes immediately — animation would leave stale frames visible.
      if (newlyCollapsed.length > 0 && newlyExpanded.length === 0) {
        nodesRef.current = updatedNodes;
        setNodes(updatedNodes);
        previousExpansionRef.current = new Set(currentExpanded);
        return;
      }

      const token = animationTokenRef.current;
      animateToPositions(nodes, updatedNodes, token, () => {
        if (token !== animationTokenRef.current) return;
        setNodes(updatedNodes);
        if (onPersistPositions) {
          onPersistPositions(updatedNodes);
        }
        setTimeout(() => fitView({ padding: 0.2, duration: 200 }), 50);
      });

      previousExpansionRef.current = new Set(currentExpanded);
    } else {
      // No expansion change - update node data but keep live positions,
      // then rebuild group frames from those positions (not arch-file coords).
      setNodes((current) => {
        nodesRef.current = current;
        const merged = mergeWithLivePositions(rawNodes, current);
        return rebuildGroupFrames(merged, currentExpanded);
      });
    }
  }, [buildNodes, expansionState?.expandedNodeIds, isInitialized, fitView, cancelAnimation, onPersistPositions]);

  const animateToPositions = (
    fromNodes: Node[],
    toNodes: Node[],
    token: number,
    onComplete: () => void
  ) => {
    const duration = 250;
    const startTime = performance.now();
    const fromPositions = new Map(fromNodes.map((n) => [n.id, n.position]));

    const animate = (currentTime: number) => {
      if (token !== animationTokenRef.current) {
        animationFrameRef.current = null;
        return;
      }

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
        animationFrameRef.current = requestAnimationFrame(animate);
      } else {
        animationFrameRef.current = null;
        if (token === animationTokenRef.current) {
          onComplete();
        }
      }
    };

    animationFrameRef.current = requestAnimationFrame(animate);
  };

  const persistPositions = useCallback(
    (nextNodes: Node[]) => {
      if (onPersistPositions) {
        onPersistPositions(nextNodes);
        return;
      }

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
    [architecture, onArchitectureChange, onPersistPositions],
  );

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      setNodes((current) => {
        const expandedIds = expansionState?.expandedNodeIds ?? new Set();
        const next = applyNodeChangesWithChildFollow(changes, current, expandedIds);

        // Check if a drag finished
        const finishedDrag = changes.some(
          (change) => change.type === "position" && change.dragging === false,
        );

        if (finishedDrag) {
          const withUpdatedFrames = rebuildGroupFrames(next, expandedIds);
          persistPositions(withUpdatedFrames);
          return withUpdatedFrames;
        }

        // During drag, update group frames in real-time
        const isDragging = changes.some(
          (change) => change.type === "position" && change.dragging === true,
        );

        if (isDragging) {
          return rebuildGroupFrames(next, expandedIds);
        }

        return next;
      });
    },
    [persistPositions, expansionState?.expandedNodeIds],
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target || !onEdgeCreate) return;
      if (connection.source.startsWith("group-") || connection.target.startsWith("group-")) {
        return;
      }

      const label = window.prompt("Describe this relationship:", "Uses");
      if (label === null) return;

      onEdgeCreate(connection.source, connection.target, label);
    },
    [onEdgeCreate],
  );

  const onNodeClick = useCallback(
    (_event: React.MouseEvent, flowNode: Node) => {
      if (flowNode.id.startsWith("group-")) return;
      const raw = (flowNode.data as { raw?: KeelNode }).raw;
      if (raw) {
        onEdgeSelect?.(null);
        onNodeSelect?.(raw);
      }
    },
    [onNodeSelect, onEdgeSelect],
  );

  const handleNodeDoubleClick = useCallback(
    (_event: React.MouseEvent, flowNode: Node) => {
      if (flowNode.id.startsWith("group-")) return;
      const raw = (flowNode.data as { raw?: KeelNode }).raw;
      if (raw) {
        const hasChildren = (flowNode.data as { hasChildren?: boolean }).hasChildren;
        if (hasChildren) {
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

  const onEdgeClick = useCallback(
    (_event: React.MouseEvent, flowEdge: Edge) => {
      const edge = architecture.edges.find((item) => item.id === flowEdge.id);
      if (!edge && composedEdges) {
        const composed = composedEdges.find((item) => item.id === flowEdge.id);
        if (composed) {
          onEdgeSelect?.(composed);
          onNodeSelect?.(null);
          return;
        }
      }
      if (edge) {
        onEdgeSelect?.(edge);
        onNodeSelect?.(null);
      }
    },
    [architecture.edges, composedEdges, onEdgeSelect, onNodeSelect],
  );

  const onPaneClick = useCallback(() => {
    onNodeSelect?.(null);
    onEdgeSelect?.(null);
  }, [onNodeSelect, onEdgeSelect]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      onNodesChange={onNodesChange}
      onConnect={onConnect}
      onEdgeClick={onEdgeClick}
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

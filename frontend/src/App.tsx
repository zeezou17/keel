/**
 * Root layout for the Keel dev UI.
 *
 * Three columns: Sidebar (requirements/ADRs) | Canvas (C4 diagram) | Sparring (AI chat).
 * Top toolbar handles navigation, git dirty state, add node, collapse all, and commit.
 *
 * FP-003: Selective drill-down replaces full level switching with expand-in-place.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import type { Node } from "@xyflow/react";

import {
  commitChanges,
  createNode,
  deleteNode,
  fetchArchitecture,
  fetchGitStatus,
  saveArchitecture,
  type ArchitectureFile,
  type KeelNode,
  type NodeType,
  type Requirement,
} from "./api/client";
import {
  type ExpansionState,
  loadExpansionState,
  saveExpansionState,
  toggleExpansion,
  collapseAll,
  collapseSubtree,
  expandMultiple,
  cacheChildArchitecture,
  getCachedArchitecture,
  composeCanvas,
  getSparringContext,
  formatAddNodeLabel,
  getAddNodeContext,
  canNodeExpand,
  getChildLevel,
  findAncestorsToExpand,
  nodeHasExpandableChildren,
  getSystemContainers,
  getLegacyOrphanContainersForSystem,
} from "./canvas/expansion";
import { buildPositionPersistRequests } from "./canvas/persistPositions";
import { buildEdgePersistRequest } from "./canvas/edgePersist";
import type { NodeEmptyContext } from "./canvas/nodeEmpty";
import { Canvas } from "./components/Canvas";
import { NodeDetailPanel } from "./components/NodeDetailPanel";
import { Sidebar } from "./components/Sidebar";
import { SparringPanel } from "./components/SparringPanel";

type ViewState = {
  level: number;
  containerId?: string | null;
  label: string;
};

const DEFAULT_NODE_TYPE: Record<number, NodeType> = {
  1: "system",
  2: "container",
  3: "component",
};

function slugify(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function defaultNodePosition(
  level: number,
  parentId: string | null,
  targetArchitecture: ArchitectureFile,
  c1Architecture: ArchitectureFile | null,
  c2Architecture: ArchitectureFile | null,
  fallbackIndex: number,
): { x: number; y: number } {
  const nodeWidth = 180;
  const nodeHeight = 80;
  const spacing = 30;

  let parentNode: KeelNode | undefined;
  if (level === 2 && parentId) {
    parentNode = c1Architecture?.nodes.find((node) => node.id === parentId);
  } else if (level === 3 && parentId) {
    parentNode = c2Architecture?.nodes.find((node) => node.id === parentId);
  }

  const siblingCount = targetArchitecture.nodes.filter((node) => {
    if (level === 2) {
      return node.parent_id === parentId;
    }
    return true;
  }).length;

  if (parentNode?.position_x != null && parentNode?.position_y != null) {
    const cols = 3;
    const col = siblingCount % cols;
    const row = Math.floor(siblingCount / cols);
    return {
      x: parentNode.position_x + col * (nodeWidth + spacing),
      y: parentNode.position_y + nodeHeight + 50 + row * (nodeHeight + spacing),
    };
  }

  return {
    x: 120 + (fallbackIndex % 5) * 220,
    y: 100 + Math.floor(fallbackIndex / 5) * 140,
  };
}

export default function App() {
  // -- Core architecture state ------------------------------------------------
  const [c1Architecture, setC1Architecture] = useState<ArchitectureFile | null>(null);
  const [c2Architecture, setC2Architecture] = useState<ArchitectureFile | null>(null);
  const [expansionState, setExpansionState] = useState<ExpansionState>(() => loadExpansionState());

  // -- UI state ---------------------------------------------------------------
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [sparCollapsed, setSparCollapsed] = useState(false);
  const [selectedRequirementId, setSelectedRequirementId] = useState<string | null>(null);
  const [highlightedNodeIds, setHighlightedNodeIds] = useState<string[]>([]);
  const [selectedNode, setSelectedNode] = useState<KeelNode | null>(null);

  // -- Legacy view state for "View all C2/C3" escape hatch --------------------
  const [fullLevelView, setFullLevelView] = useState<ViewState | null>(null);
  const [fullLevelArchitecture, setFullLevelArchitecture] = useState<ArchitectureFile | null>(null);

  // -- Persist expansion state to localStorage --------------------------------
  useEffect(() => {
    saveExpansionState(expansionState);
  }, [expansionState]);

  // -- Composed canvas from C1 + expanded children ----------------------------
  const composedCanvas = useMemo(() => {
    if (!c1Architecture) return null;
    return composeCanvas(c1Architecture, expansionState, c2Architecture);
  }, [c1Architecture, c2Architecture, expansionState]);

  // -- Sparring context based on selection/expansion --------------------------
  const sparringContext = useMemo(() => {
    if (fullLevelView) {
      return { level: fullLevelView.level, containerId: fullLevelView.containerId ?? null };
    }
    if (!c1Architecture) return { level: 1, containerId: null };
    return getSparringContext(expansionState, selectedNode, c1Architecture);
  }, [expansionState, selectedNode, c1Architecture, fullLevelView]);

  // -- Add node context -------------------------------------------------------
  const addNodeContext = useMemo(() => {
    if (fullLevelView) {
      return {
        level: fullLevelView.level,
        containerId: fullLevelView.containerId ?? null,
        parentId: null,
        focusName: fullLevelView.label,
      };
    }
    return getAddNodeContext(expansionState, selectedNode, c1Architecture, c2Architecture);
  }, [expansionState, selectedNode, fullLevelView, c1Architecture, c2Architecture]);

  const nodeEmptyContext = useMemo<NodeEmptyContext>(
    () => ({
      c1Architecture,
      c2Architecture,
      expansionState,
    }),
    [c1Architecture, c2Architecture, expansionState],
  );

  // -- Breadcrumbs for current view -------------------------------------------
  const breadcrumbs = useMemo(() => {
    const items: { label: string; action: () => void }[] = [
      {
        label: "C1 Context",
        action: () => {
          setFullLevelView(null);
          setFullLevelArchitecture(null);
          setExpansionState((prev) => collapseAll(prev));
        },
      },
    ];

    if (fullLevelView) {
      if (fullLevelView.level >= 2) {
        items.push({
          label: "View all C2",
          action: () => {
            setFullLevelView({ level: 2, label: "C2 Containers" });
            void loadFullLevel(2);
          },
        });
      }
      if (fullLevelView.level >= 3 && fullLevelView.containerId) {
        items.push({
          label: fullLevelView.label,
          action: () => {},
        });
      }
    }

    return items;
  }, [fullLevelView, expansionState]);

  // -- Load architecture ------------------------------------------------------
  const loadInitialArchitecture = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [c1Data, c2Data] = await Promise.all([
        fetchArchitecture(1),
        fetchArchitecture(2).catch(() => null),
      ]);
      setC1Architecture(c1Data);
      setC2Architecture(c2Data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load architecture");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadFullLevel = useCallback(async (level: number, containerId?: string | null) => {
    try {
      const data = await fetchArchitecture(level, containerId);
      setFullLevelArchitecture(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load architecture");
    }
  }, []);

  const refreshGitStatus = useCallback(async () => {
    try {
      const status = await fetchGitStatus();
      setDirty(status.dirty);
    } catch {
      setDirty(false);
    }
  }, []);

  useEffect(() => {
    void loadInitialArchitecture();
  }, [loadInitialArchitecture]);

  useEffect(() => {
    void refreshGitStatus();
    const interval = window.setInterval(() => {
      void refreshGitStatus();
    }, 2000);
    return () => window.clearInterval(interval);
  }, [refreshGitStatus, c1Architecture, c2Architecture]);

  // -- Persist architecture changes -------------------------------------------
  const persistArchitecture = useCallback(
    async (next: ArchitectureFile, level: number, containerId?: string | null) => {
      await saveArchitecture(level, next, containerId);
      
      // Update the correct architecture state
      if (level === 1) {
        setC1Architecture(next);
      } else if (level === 2) {
        setC2Architecture(next);
      } else if (level === 3 && containerId) {
        // Update C3 cache
        setExpansionState((prev) => cacheChildArchitecture(prev, containerId, next));
      }
      
      if (fullLevelArchitecture && fullLevelView?.level === level) {
        setFullLevelArchitecture(next);
      }
      
      await refreshGitStatus();
    },
    [refreshGitStatus, fullLevelArchitecture, fullLevelView],
  );

  // -- Expand/Collapse handlers -----------------------------------------------
  const handleNodeExpand = useCallback(
    async (node: KeelNode) => {
      if (!canNodeExpand(node)) return;

      const childLevel = getChildLevel(node);
      if (!childLevel) return;

      if (childLevel === 2) {
        if (!nodeHasExpandableChildren(node, expansionState, c2Architecture, c1Architecture)) {
          setError("This system has no containers to expand.");
          return;
        }
        setExpansionState((prev) => toggleExpansion(prev, node.id));

        // Prefetch C3 files so containers with components get chevrons
        const containers = getSystemContainers(node.id, c2Architecture, c1Architecture);
        for (const container of containers) {
          void (async () => {
            const cached = getCachedArchitecture(expansionState, container.id);
            if (cached) return;
            try {
              const c3Data = await fetchArchitecture(3, container.id);
              setExpansionState((current) => cacheChildArchitecture(current, container.id, c3Data));
            } catch {
              // No C3 file for this container — expected for most containers
            }
          })();
        }
      } else if (childLevel === 3) {
        const cached = getCachedArchitecture(expansionState, node.id);
        if (cached) {
          if (cached.nodes.length === 0) {
            setError("This container has no components to expand.");
            return;
          }
          setExpansionState((prev) => toggleExpansion(prev, node.id));
          return;
        }

        try {
          const c3Data = await fetchArchitecture(3, node.id);
          if (c3Data.nodes.length === 0) {
            setExpansionState((prev) => cacheChildArchitecture(prev, node.id, c3Data));
            setError("This container has no components to expand.");
            return;
          }
          setExpansionState((prev) => {
            const withCache = cacheChildArchitecture(prev, node.id, c3Data);
            return toggleExpansion(withCache, node.id);
          });
        } catch (err) {
          setError(err instanceof Error ? err.message : "Failed to load components");
        }
      }
    },
    [expansionState, c2Architecture, c1Architecture],
  );

  const handleNodeCollapse = useCallback((node: KeelNode) => {
    setExpansionState((prev) => collapseSubtree(prev, node, c2Architecture, c1Architecture));
  }, [c2Architecture, c1Architecture]);

  const handlePersistPositions = useCallback(
    (flowNodes: Node[]) => {
      if (!c1Architecture) return;

      const requests = buildPositionPersistRequests(
        flowNodes,
        c1Architecture,
        c2Architecture,
        expansionState,
      );

      for (const request of requests) {
        void persistArchitecture(request.architecture, request.level, request.containerId);
      }
    },
    [c1Architecture, c2Architecture, expansionState, persistArchitecture],
  );

  const handleEdgeCreate = useCallback(
    (sourceId: string, targetId: string, label: string) => {
      if (!c1Architecture) return;

      const result = buildEdgePersistRequest(
        sourceId,
        targetId,
        label,
        c1Architecture,
        c2Architecture,
        expansionState,
        composedCanvas?.nodes,
        fullLevelArchitecture,
      );

      if (!result.ok) {
        setError(result.error);
        return;
      }

      const { level, architecture, containerId } = result.request;
      void persistArchitecture(architecture, level, containerId);
    },
    [
      c1Architecture,
      c2Architecture,
      expansionState,
      composedCanvas?.nodes,
      fullLevelArchitecture,
      persistArchitecture,
    ],
  );

  const handleCollapseAll = useCallback(() => {
    setExpansionState((prev) => collapseAll(prev));
    setFullLevelView(null);
    setFullLevelArchitecture(null);
  }, []);

  // -- Escape hatch: View full level ------------------------------------------
  const handleViewFullLevel = useCallback(
    async (level: number, containerId?: string | null, label?: string) => {
      setFullLevelView({
        level,
        containerId,
        label: label ?? `C${level}`,
      });
      await loadFullLevel(level, containerId);
    },
    [loadFullLevel],
  );

  // -- Add node at focused context --------------------------------------------
  const handleAddNode = useCallback(async () => {
    const { level, containerId, parentId } = addNodeContext;
    
    // Determine which architecture to update
    let targetArchitecture: ArchitectureFile | null = null;
    if (level === 1) {
      targetArchitecture = c1Architecture;
    } else if (level === 2) {
      targetArchitecture = c2Architecture;
    } else if (level === 3 && containerId) {
      targetArchitecture = getCachedArchitecture(expansionState, containerId) ?? null;
    }

    if (!targetArchitecture) {
      // Load the architecture first if needed
      try {
        targetArchitecture = await fetchArchitecture(level, containerId);
      } catch {
        setError("Failed to load architecture for adding node");
        return;
      }
    }

    const index = targetArchitecture.nodes.length + 1;
    const nodeType = DEFAULT_NODE_TYPE[level] ?? "component";
    const name = `New ${nodeType} ${index}`;
    const position = defaultNodePosition(
      level,
      parentId,
      targetArchitecture,
      c1Architecture,
      c2Architecture,
      index,
    );
    const node: KeelNode = {
      id: `node_${slugify(name)}`,
      type: nodeType,
      level,
      name,
      description: "Describe this element.",
      paths: [],
      parent_id: level === 3 ? parentId ?? containerId ?? null : level === 2 ? parentId : null,
      position_x: position.x,
      position_y: position.y,
    };

    let architectureForCreate = targetArchitecture;
    if (level === 2 && parentId) {
      const orphans = targetArchitecture.nodes.filter(
        (existing) => existing.type === "container" && !existing.parent_id,
      );
      const legacyOrphans = getLegacyOrphanContainersForSystem(parentId, orphans, c1Architecture);
      if (legacyOrphans.length > 0) {
        const legacyIds = new Set(legacyOrphans.map((existing) => existing.id));
        architectureForCreate = {
          ...targetArchitecture,
          nodes: targetArchitecture.nodes.map((existing) =>
            legacyIds.has(existing.id) ? { ...existing, parent_id: parentId } : existing,
          ),
        };
        await saveArchitecture(level, architectureForCreate, containerId);
        if (level === 2) {
          setC2Architecture(architectureForCreate);
        }
      }
    }

    const updated = await createNode(level, node, containerId);
    
    // Update the correct state
    if (level === 1) {
      setC1Architecture(updated);
    } else if (level === 2) {
      setC2Architecture(updated);
    } else if (level === 3 && containerId) {
      setExpansionState((prev) => cacheChildArchitecture(prev, containerId, updated));
    }

    if (fullLevelView?.level === level) {
      setFullLevelArchitecture(updated);
    }

    await refreshGitStatus();
  }, [addNodeContext, c1Architecture, c2Architecture, expansionState, fullLevelView, refreshGitStatus]);

  const handleDeleteNode = useCallback(
    async (node: KeelNode) => {
      const updated = await deleteNode(node.id);

      if (updated.level === 1) {
        setC1Architecture(updated);
      } else if (updated.level === 2) {
        setC2Architecture(updated);
      } else if (updated.level === 3 && updated.container_id) {
        setExpansionState((prev) => cacheChildArchitecture(prev, updated.container_id!, updated));
      }

      if (fullLevelView?.level === updated.level) {
        setFullLevelArchitecture(updated);
      }

      setExpansionState((prev) => {
        const collapsed = collapseSubtree(prev, node, c2Architecture, c1Architecture);
        const nextExpanded = new Set(collapsed.expandedNodeIds);
        nextExpanded.delete(node.id);
        const nextCache = new Map(collapsed.childArchitectureCache);
        nextCache.delete(node.id);
        return {
          ...collapsed,
          expandedNodeIds: nextExpanded,
          childArchitectureCache: nextCache,
        };
      });

      setSelectedNode(null);
      setHighlightedNodeIds((current) => current.filter((id) => id !== node.id));
      await refreshGitStatus();
    },
    [c1Architecture, c2Architecture, fullLevelView, refreshGitStatus],
  );

  const reloadArchitecture = useCallback(async () => {
    await loadInitialArchitecture();
  }, [loadInitialArchitecture]);

  const handleCommit = useCallback(async () => {
    await commitChanges();
    await refreshGitStatus();
  }, [refreshGitStatus]);

  // -- Requirement highlight with auto-expand ---------------------------------
  const handleRequirementSelect = useCallback(
    async (requirement: Requirement | null, nodeIds: string[]) => {
      setSelectedRequirementId(requirement?.id ?? null);
      setHighlightedNodeIds(nodeIds);

      if (!requirement || nodeIds.length === 0) return;

      // Auto-expand ancestors to make highlighted nodes visible
      const allNodes = [
        ...(c1Architecture?.nodes ?? []),
        ...(c2Architecture?.nodes ?? []),
      ];

      const ancestorsToExpand: string[] = [];
      for (const nodeId of nodeIds) {
        const ancestors = findAncestorsToExpand(
          nodeId,
          allNodes,
          expansionState.expandedNodeIds
        );
        for (const ancestorId of ancestors) {
          if (!ancestorsToExpand.includes(ancestorId)) {
            ancestorsToExpand.push(ancestorId);
          }
        }
      }

      if (ancestorsToExpand.length > 0) {
        // Load any C3 architectures needed
        for (const ancestorId of ancestorsToExpand) {
          const ancestorNode = allNodes.find((n) => n.id === ancestorId);
          if (ancestorNode?.type === "container") {
            const cached = getCachedArchitecture(expansionState, ancestorId);
            if (!cached) {
              try {
                const c3Data = await fetchArchitecture(3, ancestorId);
                setExpansionState((prev) => cacheChildArchitecture(prev, ancestorId, c3Data));
              } catch {
                // Ignore errors for auto-expand
              }
            }
          }
        }
        setExpansionState((prev) => expandMultiple(prev, ancestorsToExpand));
      }
    },
    [c1Architecture, c2Architecture, expansionState],
  );

  // -- Handle architecture updates from sparring ------------------------------
  const handleSparArchitectureUpdate = useCallback(
    (updated: ArchitectureFile) => {
      if (updated.level === 1) {
        setC1Architecture(updated);
      } else if (updated.level === 2) {
        setC2Architecture(updated);
      } else if (updated.level === 3 && updated.container_id) {
        setExpansionState((prev) => cacheChildArchitecture(prev, updated.container_id!, updated));
      }
      if (fullLevelView?.level === updated.level) {
        setFullLevelArchitecture(updated);
      }
      void refreshGitStatus();
    },
    [fullLevelView, refreshGitStatus],
  );

  // -- Render -----------------------------------------------------------------
  if (loading && !c1Architecture) {
    return <div className="app-shell">Loading architecture…</div>;
  }

  if (!c1Architecture) {
    return <div className="app-shell">No architecture loaded.</div>;
  }

  // Determine which architecture to show
  const displayArchitecture = fullLevelArchitecture ?? c1Architecture;
  const displayComposedNodes = fullLevelView ? undefined : composedCanvas?.nodes;
  const displayComposedEdges = fullLevelView ? undefined : composedCanvas?.edges;

  const hasExpansions = expansionState.expandedNodeIds.size > 0 || fullLevelView !== null;

  return (
    <div className="app-shell">
      <header className="toolbar">
        <div className="breadcrumbs">
          {breadcrumbs.map((crumb, index) => (
            <button
              key={crumb.label}
              className="breadcrumb"
              onClick={crumb.action}
            >
              {crumb.label}
              {index < breadcrumbs.length - 1 ? " / " : ""}
            </button>
          ))}
          {!fullLevelView && expansionState.expandedNodeIds.size > 0 && (
            <span style={{ color: "#829ab1", fontSize: "0.85rem", marginLeft: "0.5rem" }}>
              · {expansionState.expandedNodeIds.size} expanded
            </span>
          )}
        </div>
        <div className="toolbar-actions">
          {dirty ? <span className="dirty-indicator">Uncommitted changes</span> : null}
          {hasExpansions && (
            <button className="collapse-all-button" onClick={handleCollapseAll}>
              Collapse all
            </button>
          )}
          {!fullLevelView && (
            <button
              className="breadcrumb"
              onClick={() => void handleViewFullLevel(2, null, "C2 Containers")}
              title="View all C2 containers (classic C4 view)"
            >
              View all C2
            </button>
          )}
          <button onClick={() => void handleAddNode()}>
            {formatAddNodeLabel(addNodeContext)}
          </button>
          <button onClick={() => void handleCommit()} disabled={!dirty}>
            Commit
          </button>
        </div>
      </header>
      {error ? <div className="error-banner">{error}</div> : null}
      <div className="workspace">
        <Sidebar
          selectedRequirementId={selectedRequirementId}
          onRequirementSelect={handleRequirementSelect}
          onArchitectureRefresh={() => void reloadArchitecture()}
        />
        <main className="canvas-panel">
          <Canvas
            architecture={displayArchitecture}
            composedNodes={displayComposedNodes}
            composedEdges={displayComposedEdges}
            expansionState={expansionState}
            highlightedNodeIds={highlightedNodeIds}
            selectedNodeId={selectedNode?.id ?? null}
            onArchitectureChange={(next, level, containerId) => void persistArchitecture(next, level, containerId)}
            onPersistPositions={handlePersistPositions}
            onEdgeCreate={handleEdgeCreate}
            onNodeSelect={(node) => setSelectedNode(node)}
            onNodeExpand={(node) => void handleNodeExpand(node)}
            onNodeCollapse={handleNodeCollapse}
            onNodeDoubleClick={() => {}}
          />
          <NodeDetailPanel
            node={selectedNode}
            isExpanded={selectedNode ? expansionState.expandedNodeIds.has(selectedNode.id) : false}
            canExpand={selectedNode ? nodeHasExpandableChildren(selectedNode, expansionState, c2Architecture, c1Architecture) : false}
            emptyContext={nodeEmptyContext}
            onExpand={(node) => void handleNodeExpand(node)}
            onCollapse={handleNodeCollapse}
            onDelete={handleDeleteNode}
            onClose={() => setSelectedNode(null)}
            onGenerated={() => void refreshGitStatus()}
          />
        </main>
        <SparringPanel
          level={sparringContext.level}
          containerId={sparringContext.containerId}
          collapsed={sparCollapsed}
          onToggleCollapsed={() => setSparCollapsed((value) => !value)}
          onArchitectureUpdated={handleSparArchitectureUpdate}
        />
      </div>
    </div>
  );
}

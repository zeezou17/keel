/**
 * Root layout for the Keel dev UI.
 *
 * Three columns: Sidebar (requirements/ADRs) | Canvas (C4 diagram) | Sparring (AI chat).
 * Top toolbar handles navigation, git dirty state, add node, collapse all, and commit.
 *
 * FP-003: Selective drill-down replaces full level switching with expand-in-place.
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  commitChanges,
  createNode,
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
  expandMultiple,
  cacheChildArchitecture,
  getCachedArchitecture,
  composeCanvas,
  getSparringContext,
  getAddNodeContext,
  canNodeExpand,
  getChildLevel,
  findAncestorsToExpand,
} from "./canvas/expansion";
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
      };
    }
    return getAddNodeContext(expansionState, selectedNode);
  }, [expansionState, selectedNode, fullLevelView]);

  // -- Breadcrumbs for current view -------------------------------------------
  const breadcrumbs = useMemo(() => {
    const items: { label: string; action: () => void }[] = [
      {
        label: "C1 Context",
        action: () => {
          setFullLevelView(null);
          setFullLevelArchitecture(null);
          setExpansionState(collapseAll(expansionState));
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

      // Load child architecture if not cached
      if (childLevel === 2) {
        // C2 is already loaded globally
        setExpansionState((prev) => toggleExpansion(prev, node.id));
      } else if (childLevel === 3) {
        // Load C3 for this container
        const cached = getCachedArchitecture(expansionState, node.id);
        if (!cached) {
          try {
            const c3Data = await fetchArchitecture(3, node.id);
            setExpansionState((prev) => {
              const withCache = cacheChildArchitecture(prev, node.id, c3Data);
              return toggleExpansion(withCache, node.id);
            });
          } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load components");
          }
        } else {
          setExpansionState((prev) => toggleExpansion(prev, node.id));
        }
      }
    },
    [expansionState],
  );

  const handleNodeCollapse = useCallback((node: KeelNode) => {
    setExpansionState((prev) => toggleExpansion(prev, node.id));
  }, []);

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
    const { level, containerId } = addNodeContext;
    
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
    const node: KeelNode = {
      id: `node_${slugify(name)}`,
      type: nodeType,
      level,
      name,
      description: "Describe this element.",
      paths: [],
      parent_id: level === 3 ? containerId ?? null : null,
      position_x: 120 + (index % 5) * 220,
      position_y: 100 + Math.floor(index / 5) * 140,
    };

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
            Add node {addNodeContext.level > 1 ? `(C${addNodeContext.level})` : ""}
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
            expansionState={expansionState}
            highlightedNodeIds={highlightedNodeIds}
            selectedNodeId={selectedNode?.id ?? null}
            onArchitectureChange={(next, level, containerId) => void persistArchitecture(next, level, containerId)}
            onNodeSelect={setSelectedNode}
            onNodeExpand={(node) => void handleNodeExpand(node)}
            onNodeCollapse={handleNodeCollapse}
            onNodeDoubleClick={() => {}}
          />
          <NodeDetailPanel
            node={selectedNode}
            isExpanded={selectedNode ? expansionState.expandedNodeIds.has(selectedNode.id) : false}
            canExpand={selectedNode ? canNodeExpand(selectedNode) : false}
            onExpand={(node) => void handleNodeExpand(node)}
            onCollapse={handleNodeCollapse}
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

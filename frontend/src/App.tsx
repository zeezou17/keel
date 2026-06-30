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
} from "./api/client";
import { Canvas } from "./components/Canvas";
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
  const [view, setView] = useState<ViewState>({ level: 1, label: "C1 Context" });
  const [architecture, setArchitecture] = useState<ArchitectureFile | null>(null);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [sparCollapsed, setSparCollapsed] = useState(false);

  const breadcrumbs = useMemo(() => {
    const items: ViewState[] = [{ level: 1, label: "C1 Context" }];
    if (view.level >= 2) {
      items.push({ level: 2, label: "C2 Containers" });
    }
    if (view.level >= 3) {
      items.push({ level: 3, containerId: view.containerId, label: view.label });
    }
    return items;
  }, [view]);

  const loadView = useCallback(async (nextView: ViewState) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchArchitecture(nextView.level, nextView.containerId);
      setArchitecture(data);
      setView(nextView);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load architecture");
    } finally {
      setLoading(false);
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
    void loadView({ level: 1, label: "C1 Context" });
  }, [loadView]);

  useEffect(() => {
    void refreshGitStatus();
    const interval = window.setInterval(() => {
      void refreshGitStatus();
    }, 2000);
    return () => window.clearInterval(interval);
  }, [refreshGitStatus, architecture]);

  const persistArchitecture = useCallback(
    async (next: ArchitectureFile) => {
      setArchitecture(next);
      await saveArchitecture(view.level, next, view.containerId);
      await refreshGitStatus();
    },
    [refreshGitStatus, view.containerId, view.level],
  );

  const handleNodeOpen = useCallback(
    async (node: KeelNode) => {
      if (view.level === 1 && node.type === "system") {
        await loadView({ level: 2, label: "C2 Containers" });
        return;
      }
      if (view.level === 2 && node.type === "container") {
        await loadView({
          level: 3,
          containerId: node.id,
          label: `C3 ${node.name}`,
        });
      }
    },
    [loadView, view.level],
  );

  const handleAddNode = useCallback(async () => {
    if (!architecture) {
      return;
    }
    const index = architecture.nodes.length + 1;
    const nodeType = DEFAULT_NODE_TYPE[view.level] ?? "component";
    const name = `New ${nodeType} ${index}`;
    const node: KeelNode = {
      id: `node_${slugify(name)}`,
      type: nodeType,
      level: view.level,
      name,
      description: "Describe this element.",
      paths: [],
      parent_id: view.level === 3 ? view.containerId ?? null : null,
      position_x: 120 + (index % 5) * 220,
      position_y: 100 + Math.floor(index / 5) * 140,
    };
    const updated = await createNode(view.level, node, view.containerId);
    setArchitecture(updated);
    await refreshGitStatus();
  }, [architecture, refreshGitStatus, view.containerId, view.level]);

  const handleCommit = useCallback(async () => {
    await commitChanges();
    await refreshGitStatus();
  }, [refreshGitStatus]);

  if (loading && !architecture) {
    return <div className="app-shell">Loading architecture…</div>;
  }

  if (!architecture) {
    return <div className="app-shell">No architecture loaded.</div>;
  }

  return (
    <div className="app-shell">
      <header className="toolbar">
        <div className="breadcrumbs">
          {breadcrumbs.map((crumb, index) => (
            <button
              key={`${crumb.level}-${crumb.containerId ?? "root"}`}
              className="breadcrumb"
              onClick={() => void loadView(crumb)}
            >
              {crumb.label}
              {index < breadcrumbs.length - 1 ? " / " : ""}
            </button>
          ))}
        </div>
        <div className="toolbar-actions">
          {dirty ? <span className="dirty-indicator">Uncommitted changes</span> : null}
          <button onClick={() => void handleAddNode()}>Add node</button>
          <button onClick={() => void handleCommit()} disabled={!dirty}>
            Commit
          </button>
        </div>
      </header>
      {error ? <div className="error-banner">{error}</div> : null}
      <div className="workspace">
        <main className="canvas-panel">
          <Canvas
            architecture={architecture}
            onArchitectureChange={(next) => void persistArchitecture(next)}
            onNodeOpen={(node) => void handleNodeOpen(node)}
          />
        </main>
        <SparringPanel
          level={view.level}
          containerId={view.containerId}
          collapsed={sparCollapsed}
          onToggleCollapsed={() => setSparCollapsed((value) => !value)}
          onArchitectureUpdated={(updated) => {
            setArchitecture(updated);
            void refreshGitStatus();
          }}
        />
      </div>
    </div>
  );
}

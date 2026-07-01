/**
 * Left sidebar with tabs for Requirements, ADRs, and Characteristics.
 * Each tab loads a separate panel component that edits `.keel/` markdown/yaml.
 */
import { useState } from "react";

import type { Requirement } from "../api/client";
import { ADRsPanel } from "./ADRsPanel";
import { CharacteristicsPanel } from "./CharacteristicsPanel";
import { RequirementsPanel } from "./RequirementsPanel";

type SidebarTab = "requirements" | "adrs" | "characteristics";

interface SidebarProps {
  onRequirementSelect: (requirement: Requirement | null, highlightedNodeIds: string[]) => void;
  selectedRequirementId: string | null;
  onArchitectureRefresh: () => void;
}

export function Sidebar({
  onRequirementSelect,
  selectedRequirementId,
  onArchitectureRefresh,
}: SidebarProps) {
  const [tab, setTab] = useState<SidebarTab>("requirements");
  const [collapsed, setCollapsed] = useState(false);

  if (collapsed) {
    return (
      <aside className="sidebar collapsed">
        <button onClick={() => setCollapsed(false)}>Docs</button>
      </aside>
    );
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-tabs">
          <button className={tab === "requirements" ? "active" : ""} onClick={() => setTab("requirements")}>
            Requirements
          </button>
          <button className={tab === "adrs" ? "active" : ""} onClick={() => setTab("adrs")}>
            ADRs
          </button>
          <button
            className={tab === "characteristics" ? "active" : ""}
            onClick={() => setTab("characteristics")}
          >
            Characteristics
          </button>
        </div>
        <button onClick={() => setCollapsed(true)}>Collapse</button>
      </div>
      {tab === "requirements" ? (
        <RequirementsPanel
          selectedId={selectedRequirementId}
          onSelect={onRequirementSelect}
          onArchitectureRefresh={onArchitectureRefresh}
        />
      ) : null}
      {tab === "adrs" ? <ADRsPanel /> : null}
      {tab === "characteristics" ? <CharacteristicsPanel /> : null}
    </aside>
  );
}

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { KeelNode } from "../api/client";
import { NodeDetailPanel } from "./NodeDetailPanel";

const baseNode: KeelNode = {
  id: "node_a",
  type: "system",
  level: 1,
  name: "System A",
  description: "First system",
  paths: [],
};

const otherNode: KeelNode = {
  id: "node_b",
  type: "system",
  level: 1,
  name: "System B",
  description: "Second system",
  paths: [],
  req_ids: ["REQ-001"],
};

const emptyContext = {
  c1Architecture: null,
  c2Architecture: null,
  expansionState: { expandedNodeIds: new Set<string>(), childArchitectureCache: new Map() },
};

describe("NodeDetailPanel", () => {
  it("clears error feedback when a different node is selected", () => {
    const { rerender } = render(
      <NodeDetailPanel
        node={baseNode}
        isExpanded={false}
        canExpand={false}
        emptyContext={emptyContext}
        onExpand={vi.fn()}
        onCollapse={vi.fn()}
        onSave={vi.fn()}
        onDelete={vi.fn()}
        onClose={vi.fn()}
        onGenerated={vi.fn()}
      />,
    );

    screen.getByRole("button", { name: "Generate work package" }).click();
    expect(
      screen.getByText(/no linked requirements/i),
    ).toBeTruthy();

    rerender(
      <NodeDetailPanel
        node={otherNode}
        isExpanded={false}
        canExpand={false}
        emptyContext={emptyContext}
        onExpand={vi.fn()}
        onCollapse={vi.fn()}
        onSave={vi.fn()}
        onDelete={vi.fn()}
        onClose={vi.fn()}
        onGenerated={vi.fn()}
      />,
    );

    expect(screen.queryByText(/no linked requirements/i)).toBeNull();
    expect(screen.getByText("System B")).toBeTruthy();
  });
});

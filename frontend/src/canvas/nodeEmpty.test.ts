import { describe, expect, it } from "vitest";

import type { ArchitectureFile, KeelNode } from "../api/client";
import { createExpansionState } from "./expansion";
import {
  buildDeleteConfirmMessage,
  getNodeNonemptyReasons,
  isNodeEmpty,
} from "./nodeEmpty";

const emptyNode: KeelNode = {
  id: "node_new-system",
  type: "system",
  level: 1,
  name: "New system 1",
  description: "Describe this element.",
  paths: [],
};

const c1Architecture: ArchitectureFile = {
  schema_version: 1,
  level: 1,
  nodes: [emptyNode],
  edges: [],
};

describe("isNodeEmpty", () => {
  it("returns true for a node with no edges, children, or links", () => {
    expect(
      isNodeEmpty(emptyNode, {
        c1Architecture,
        c2Architecture: null,
        expansionState: createExpansionState(),
      }),
    ).toBe(true);
  });

  it("returns false when the node has connected edges", () => {
    const architecture: ArchitectureFile = {
      ...c1Architecture,
      edges: [
        {
          id: "edge_1",
          type: "uses",
          source_id: "node_person",
          target_id: emptyNode.id,
        },
      ],
    };

    expect(
      isNodeEmpty(emptyNode, {
        c1Architecture: architecture,
        c2Architecture: null,
        expansionState: createExpansionState(),
      }),
    ).toBe(false);
  });

  it("returns false when a system has child containers", () => {
    const c2Architecture: ArchitectureFile = {
      schema_version: 1,
      level: 2,
      nodes: [
        {
          id: "node_api",
          type: "container",
          level: 2,
          name: "API",
          description: "API container",
          paths: [],
          parent_id: emptyNode.id,
        },
      ],
      edges: [],
    };

    expect(
      isNodeEmpty(emptyNode, {
        c1Architecture,
        c2Architecture,
        expansionState: createExpansionState(),
      }),
    ).toBe(false);
  });
});

describe("buildDeleteConfirmMessage", () => {
  it("lists why confirmation is required", () => {
    const message = buildDeleteConfirmMessage(emptyNode, [
      { kind: "edges", count: 2 },
      { kind: "requirements", count: 1 },
    ]);

    expect(message).toContain('Delete "New system 1"');
    expect(message).toContain("2 connected edges");
    expect(message).toContain("1 linked requirement");
  });
});

describe("getNodeNonemptyReasons", () => {
  it("includes path globs as a non-empty reason", () => {
    const node: KeelNode = {
      ...emptyNode,
      paths: ["src/**"],
    };

    const reasons = getNodeNonemptyReasons(node, {
      c1Architecture: { ...c1Architecture, nodes: [node] },
      c2Architecture: null,
      expansionState: createExpansionState(),
    });

    expect(reasons).toEqual([{ kind: "paths", count: 1 }]);
  });
});

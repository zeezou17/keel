import { describe, expect, it } from "vitest";

import type { ArchitectureFile } from "../api/client";
import { createExpansionState } from "./expansion";
import { buildEdgeDeleteRequest, buildEdgePersistRequest, buildEdgeUpdateRequest, locateEdge } from "./edgePersist";

const c1: ArchitectureFile = {
  schema_version: 1,
  level: 1,
  nodes: [
    {
      id: "sys_a",
      type: "system",
      level: 1,
      name: "Payments",
      description: "",
      paths: [],
    },
    {
      id: "sys_b",
      type: "system",
      level: 1,
      name: "Inventory",
      description: "",
      paths: [],
    },
  ],
  edges: [],
};

const c2: ArchitectureFile = {
  schema_version: 1,
  level: 2,
  nodes: [
    {
      id: "ctr_api",
      type: "container",
      level: 2,
      name: "API",
      description: "",
      paths: [],
      parent_id: "sys_a",
    },
    {
      id: "ctr_worker",
      type: "container",
      level: 2,
      name: "Worker",
      description: "",
      paths: [],
      parent_id: "sys_a",
    },
  ],
  edges: [],
};

describe("buildEdgePersistRequest", () => {
  it("creates a C2 edge when both containers are visible in the composed canvas", () => {
    const composedNodes = [
      { ...c1.nodes[0], depth: 1, parentGroupId: null, isExpanded: true, hasChildren: true },
      { ...c2.nodes[0], depth: 2, parentGroupId: "sys_a", isExpanded: false, hasChildren: false },
      { ...c2.nodes[1], depth: 2, parentGroupId: "sys_a", isExpanded: false, hasChildren: false },
    ];

    const result = buildEdgePersistRequest(
      "ctr_api",
      "ctr_worker",
      "Publishes to",
      c1,
      c2,
      createExpansionState(),
      composedNodes,
    );

    expect(result.ok).toBe(true);
    if (!result.ok) return;

    expect(result.request.level).toBe(2);
    expect(result.request.architecture.edges).toHaveLength(1);
    expect(result.request.architecture.edges[0]).toMatchObject({
      source_id: "ctr_api",
      target_id: "ctr_worker",
      label: "Publishes to",
    });
  });

  it("rejects cross-level links", () => {
    const composedNodes = [
      { ...c1.nodes[0], depth: 1, parentGroupId: null, isExpanded: true, hasChildren: true },
      { ...c2.nodes[0], depth: 2, parentGroupId: "sys_a", isExpanded: false, hasChildren: false },
    ];

    const result = buildEdgePersistRequest(
      "sys_a",
      "ctr_api",
      "Uses",
      c1,
      c2,
      createExpansionState(),
      composedNodes,
    );

    expect(result).toEqual({
      ok: false,
      error: "Links must connect nodes at the same C4 level.",
    });
  });
});

describe("buildEdgeUpdateRequest", () => {
  it("updates an existing C1 edge label", () => {
    const withEdge: ArchitectureFile = {
      ...c1,
      edges: [
        {
          id: "edge_sys",
          type: "dependency",
          source_id: "sys_a",
          target_id: "sys_b",
          label: "Uses",
        },
      ],
    };

    const result = buildEdgeUpdateRequest(
      "edge_sys",
      "Calls API",
      withEdge,
      c2,
      createExpansionState(),
    );

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.request.architecture.edges[0].label).toBe("Calls API");
  });
});

describe("buildEdgeDeleteRequest", () => {
  it("removes an edge from C2 architecture", () => {
    const withEdge: ArchitectureFile = {
      ...c2,
      edges: [
        {
          id: "edge_ctr",
          type: "dependency",
          source_id: "ctr_api",
          target_id: "ctr_worker",
          label: "Publishes to",
        },
      ],
    };

    const result = buildEdgeDeleteRequest(
      "edge_ctr",
      c1,
      withEdge,
      createExpansionState(),
    );

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.request.architecture.edges).toHaveLength(0);
  });
});

describe("locateEdge", () => {
  it("finds edges in overview architecture", () => {
    const overview: ArchitectureFile = {
      ...c2,
      edges: [
        {
          id: "edge_overview",
          type: "dependency",
          source_id: "ctr_api",
          target_id: "ctr_worker",
          label: "Uses",
        },
      ],
    };

    const location = locateEdge("edge_overview", c1, c2, createExpansionState(), overview);
    expect(location?.edge.id).toBe("edge_overview");
    expect(location?.level).toBe(2);
  });
});

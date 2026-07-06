import { describe, expect, it, vi } from "vitest";

import type { ArchitectureFile, KeelNode } from "../api/client";
import {
  cacheChildArchitecture,
  collapseSubtree,
  composeCanvas,
  createExpansionState,
  expandNode,
  getLegacyPrimarySystemId,
  getSystemContainers,
  loadExpansionState,
  nodeHasExpandableChildren,
} from "./expansion";

const system: KeelNode = {
  id: "sys_1",
  type: "system",
  level: 1,
  name: "Kryptonite",
  description: "Main system",
  paths: [],
};

const containerA: KeelNode = {
  id: "ctr_a",
  type: "container",
  level: 2,
  name: "Web API",
  description: "API",
  paths: [],
  parent_id: "sys_1",
};

const containerB: KeelNode = {
  id: "ctr_b",
  type: "container",
  level: 2,
  name: "Local Data Store",
  description: "DB",
  paths: [],
  parent_id: "sys_1",
  position_x: 50,
  position_y: 40,
};

const external: KeelNode = {
  id: "ext_1",
  type: "external",
  level: 2,
  name: "Android Device",
  description: "External",
  paths: [],
};

const c1: ArchitectureFile = {
  schema_version: 1,
  level: 1,
  nodes: [system],
  edges: [],
};

const c2: ArchitectureFile = {
  schema_version: 1,
  level: 2,
  nodes: [containerA, containerB, external],
  edges: [],
};

describe("getSystemContainers", () => {
  it("returns only containers for the system, not externals", () => {
    const containers = getSystemContainers("sys_1", c2, c1);
    expect(containers.map((n) => n.id)).toEqual(["ctr_a", "ctr_b"]);
  });

  it("returns no legacy containers for a non-sole system when parent_id is missing", () => {
    const legacyC2: ArchitectureFile = {
      schema_version: 1,
      level: 2,
      nodes: [
        { ...containerA, parent_id: undefined },
        { ...containerB, parent_id: undefined },
        external,
      ],
      edges: [],
    };
    const multiC1: ArchitectureFile = {
      ...c1,
      nodes: [
        system,
        {
          id: "sys_2",
          type: "system",
          level: 1,
          name: "Other",
          description: "",
          paths: [],
        },
      ],
      edges: [
        {
          id: "e1",
          type: "uses",
          source_id: "ext_1",
          target_id: "sys_1",
        },
      ],
    };

    expect(getLegacyPrimarySystemId(multiC1)).toBe("sys_1");
    expect(getSystemContainers("sys_1", legacyC2, multiC1).map((n) => n.id)).toEqual([
      "ctr_a",
      "ctr_b",
    ]);
    expect(getSystemContainers("sys_2", legacyC2, multiC1)).toEqual([]);
  });

  it("returns all legacy containers for the sole C1 system", () => {
    expect(getSystemContainers("sys_1", c2, c1).length).toBe(2);
  });
});

describe("nodeHasExpandableChildren", () => {
  it("is true for a system with containers", () => {
    const state = createExpansionState();
    expect(nodeHasExpandableChildren(system, state, c2)).toBe(true);
  });

  it("is false for a container without cached C3 components", () => {
    const state = createExpansionState();
    expect(nodeHasExpandableChildren(containerA, state, c2)).toBe(false);
  });

  it("is true for a container with cached C3 components", () => {
    let state = createExpansionState();
    state = cacheChildArchitecture(state, "ctr_a", {
      schema_version: 1,
      level: 3,
      container_id: "ctr_a",
      nodes: [
        {
          id: "cmp_1",
          type: "component",
          level: 3,
          name: "Handler",
          description: "",
          paths: [],
          parent_id: "ctr_a",
        },
      ],
      edges: [],
    });
    expect(nodeHasExpandableChildren(containerA, state, c2)).toBe(true);
  });

  it("is false for a container with an empty cached C3 file", () => {
    let state = createExpansionState();
    state = cacheChildArchitecture(state, "ctr_a", {
      schema_version: 1,
      level: 3,
      container_id: "ctr_a",
      nodes: [],
      edges: [],
    });
    expect(nodeHasExpandableChildren(containerA, state, c2)).toBe(false);
  });
});

describe("composeCanvas", () => {
  it("does not inline externals when a system is expanded", () => {
    let state = createExpansionState();
    state = expandNode(state, "sys_1");

    const { nodes } = composeCanvas(c1, state, c2);
    const childIds = nodes.filter((n) => n.parentGroupId).map((n) => n.id);

    expect(childIds).toEqual(["ctr_a", "ctr_b"]);
    expect(nodes.find((n) => n.id === "ext_1")).toBeUndefined();
  });

  it("omits children when the parent system is collapsed", () => {
    const state = createExpansionState();
    const { nodes } = composeCanvas(c1, state, c2);

    expect(nodes.map((n) => n.id)).toEqual(["sys_1"]);
  });

  it("marks containers without C3 as not expandable", () => {
    let state = createExpansionState();
    state = expandNode(state, "sys_1");

    const { nodes } = composeCanvas(c1, state, c2);
    const webApi = nodes.find((n) => n.id === "ctr_a");

    expect(webApi?.hasChildren).toBe(false);
  });
});

describe("collapseSubtree", () => {
  it("removes the system and expanded child containers from expansion state", () => {
    let state = createExpansionState();
    state = expandNode(state, "sys_1");
    state = expandNode(state, "ctr_a");

    state = collapseSubtree(state, system, c2, c1);

    expect(state.expandedNodeIds.has("sys_1")).toBe(false);
    expect(state.expandedNodeIds.has("ctr_a")).toBe(false);
  });

  it("is a no-op when the node is already collapsed", () => {
    const state = createExpansionState();
    const next = collapseSubtree(state, system, c2, c1);
    expect(next).toBe(state);
  });
});

describe("loadExpansionState", () => {
  it("starts fresh and clears stale localStorage", () => {
    const storage = new Map<string, string>();
    const fakeStorage = {
      removeItem: (key: string) => { storage.delete(key); },
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => { storage.set(key, value); },
    };
    vi.stubGlobal("localStorage", fakeStorage);
    fakeStorage.setItem("keel:expansion-state", '{"expandedNodeIds":["sys_1"]}');

    const state = loadExpansionState();

    expect(state.expandedNodeIds.size).toBe(0);
    expect(fakeStorage.getItem("keel:expansion-state")).toBeNull();

    vi.unstubAllGlobals();
  });
});

describe("composeCanvas child positions", () => {
  it("preserves arch-file coordinates on composed children (layout overwrites on expand)", () => {
    let state = createExpansionState();
    state = expandNode(state, "sys_1");

    const { nodes } = composeCanvas(c1, state, c2);
    const db = nodes.find((n) => n.id === "ctr_b");

    expect(db?.position_x).toBe(50);
    expect(db?.position_y).toBe(40);
  });
});

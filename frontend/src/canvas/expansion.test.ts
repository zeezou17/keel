import { describe, expect, it } from "vitest";

import type { ArchitectureFile } from "../api/client";
import {
  cacheChildArchitecture,
  createExpansionState,
  expandNode,
  formatAddNodeLabel,
  getAddNodeContext,
} from "./expansion";

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
  ],
  edges: [],
};

describe("getAddNodeContext", () => {
  it("defaults to C1 when nothing is expanded or selected", () => {
    const state = createExpansionState();
    expect(getAddNodeContext(state, null, c1, c2)).toEqual({
      level: 1,
      containerId: null,
      parentId: null,
      focusName: null,
    });
  });

  it("targets C2 under the selected expanded system", () => {
    let state = createExpansionState();
    state = expandNode(state, "sys_a");

    expect(getAddNodeContext(state, c1.nodes[0], c1, c2)).toEqual({
      level: 2,
      containerId: null,
      parentId: "sys_a",
      focusName: "Payments",
    });
  });

  it("targets C3 for a selected container", () => {
    const state = createExpansionState();

    expect(getAddNodeContext(state, c2.nodes[0], c1, c2)).toEqual({
      level: 3,
      containerId: "ctr_api",
      parentId: "ctr_api",
      focusName: "API",
    });
  });

  it("uses the most recently expanded system when multiple are open", () => {
    let state = createExpansionState();
    state = expandNode(state, "sys_a");
    state = expandNode(state, "sys_b");

    expect(getAddNodeContext(state, null, c1, c2)).toEqual({
      level: 2,
      containerId: null,
      parentId: "sys_b",
      focusName: "Inventory",
    });
  });

  it("prefers the selected node over expanded-set iteration order", () => {
    let state = createExpansionState();
    state = expandNode(state, "sys_b");
    state = expandNode(state, "sys_a");

    expect(getAddNodeContext(state, c1.nodes[0], c1, c2)).toEqual({
      level: 2,
      containerId: null,
      parentId: "sys_a",
      focusName: "Payments",
    });
  });

  it("targets C3 when the last expanded node is a container", () => {
    let state = createExpansionState();
    state = expandNode(state, "sys_a");
    state = expandNode(state, "ctr_api");
    state = cacheChildArchitecture(state, "ctr_api", {
      schema_version: 1,
      level: 3,
      container_id: "ctr_api",
      nodes: [],
      edges: [],
    });

    expect(getAddNodeContext(state, null, c1, c2)).toEqual({
      level: 3,
      containerId: "ctr_api",
      parentId: "ctr_api",
      focusName: "API",
    });
  });
});

describe("formatAddNodeLabel", () => {
  it("includes the focused node name in the toolbar label", () => {
    expect(
      formatAddNodeLabel({
        level: 2,
        containerId: null,
        parentId: "sys_a",
        focusName: "Payments",
      }),
    ).toBe("Add node (C2 · Payments)");
  });
});

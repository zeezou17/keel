import type { Node } from "@xyflow/react";
import { describe, expect, it } from "vitest";

import type { ArchitectureFile } from "../api/client";
import { cacheChildArchitecture, createExpansionState } from "./expansion";
import { buildPositionPersistRequests } from "./persistPositions";

function flowNode(
  id: string,
  position: { x: number; y: number },
  data: Record<string, unknown>,
): Node {
  return { id, type: "expandable", position, data };
}

const c1: ArchitectureFile = {
  schema_version: 1,
  level: 1,
  nodes: [
    {
      id: "sys_1",
      type: "system",
      level: 1,
      name: "System",
      description: "",
      paths: [],
      position_x: 100,
      position_y: 100,
    },
  ],
  edges: [],
};

const c2: ArchitectureFile = {
  schema_version: 1,
  level: 2,
  nodes: [
    {
      id: "ctr_a",
      type: "container",
      level: 2,
      name: "API",
      description: "",
      paths: [],
      parent_id: "sys_1",
      position_x: 0,
      position_y: 0,
    },
  ],
  edges: [],
};

describe("buildPositionPersistRequests", () => {
  it("persists C1 and C2 node positions separately", () => {
    const state = createExpansionState();
    const flowNodes = [
      flowNode("sys_1", { x: 200, y: 150 }, { raw: c1.nodes[0], parentGroupId: null }),
      flowNode("ctr_a", { x: 420, y: 360 }, {
        raw: c2.nodes[0],
        parentGroupId: "sys_1",
      }),
    ];

    const requests = buildPositionPersistRequests(flowNodes, c1, c2, state);
    const levels = requests.map((request) => request.level).sort();

    expect(levels).toEqual([1, 2]);
    expect(requests.find((request) => request.level === 2)?.architecture.nodes[0].position_x).toBe(420);
  });

  it("persists C3 positions into the cached container architecture", () => {
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

    const flowNodes = [
      flowNode("cmp_1", { x: 500, y: 500 }, {
        raw: state.childArchitectureCache.get("ctr_a")!.nodes[0],
        parentGroupId: "ctr_a",
      }),
    ];

    const requests = buildPositionPersistRequests(flowNodes, c1, c2, state);
    const c3 = requests.find((request) => request.level === 3);

    expect(c3?.containerId).toBe("ctr_a");
    expect(c3?.architecture.nodes[0].position_x).toBe(500);
  });

  it("ignores synthetic group nodes", () => {
    const state = createExpansionState();
    const flowNodes = [
      {
        id: "group-sys_1",
        type: "default",
        position: { x: 0, y: 0 },
        data: { label: "" },
      },
      flowNode("sys_1", { x: 210, y: 160 }, { raw: c1.nodes[0], parentGroupId: null }),
    ];

    const requests = buildPositionPersistRequests(flowNodes, c1, c2, state);

    expect(requests).toHaveLength(1);
    expect(requests[0].level).toBe(1);
  });
});

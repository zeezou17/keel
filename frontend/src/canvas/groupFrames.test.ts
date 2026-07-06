import type { Node } from "@xyflow/react";
import { describe, expect, it } from "vitest";

import { mergeWithLivePositions, rebuildGroupFrames } from "./groupFrames";

function flowNode(
  id: string,
  position: { x: number; y: number },
  data: Record<string, unknown> = {},
): Node {
  return { id, type: "expandable", position, data };
}

describe("mergeWithLivePositions", () => {
  it("keeps canvas positions instead of arch-file defaults", () => {
    const raw = [
      flowNode("ctr_a", { x: 0, y: 0 }),
      flowNode("ctr_b", { x: 0, y: 0 }),
    ];
    const live = [
      flowNode("ctr_a", { x: 400, y: 330 }),
      flowNode("ctr_b", { x: 610, y: 330 }),
    ];

    const merged = mergeWithLivePositions(raw, live);

    expect(merged[0].position).toEqual({ x: 400, y: 330 });
    expect(merged[1].position).toEqual({ x: 610, y: 330 });
  });
});

describe("rebuildGroupFrames", () => {
  it("creates a group frame around expanded children at live positions", () => {
    const nodes = [
      flowNode("sys_1", { x: 400, y: 100 }, { depth: 1, label: "Kryptonite" }),
      flowNode("ctr_a", { x: 400, y: 330 }, { parentGroupId: "sys_1" }),
      flowNode("ctr_b", { x: 610, y: 330 }, { parentGroupId: "sys_1" }),
    ];

    const result = rebuildGroupFrames(nodes, new Set(["sys_1"]));
    const frame = result.find((n) => n.id === "group-sys_1");
    const header = result.find((n) => n.id === "group-header-sys_1");

    expect(frame).toBeDefined();
    expect(header).toBeDefined();
    expect((frame?.position.x ?? 0)).toBeGreaterThan(350);
    expect((header?.data as { label: string }).label).toContain("2 children");
  });

  it("removes group frames when the parent is collapsed", () => {
    const nodes = [
      flowNode("sys_1", { x: 400, y: 100 }, { depth: 1, label: "Kryptonite" }),
      {
        id: "group-sys_1",
        type: "default",
        position: { x: 0, y: 0 },
        data: { label: "" },
      },
      {
        id: "group-header-sys_1",
        type: "default",
        position: { x: 0, y: -28 },
        data: { label: "stale" },
      },
    ];

    const result = rebuildGroupFrames(nodes, new Set());

    expect(result.some((n) => n.id.startsWith("group-"))).toBe(false);
    expect(result).toHaveLength(1);
  });

  it("does not create a group for an expanded node with no visible children", () => {
    const nodes = [
      flowNode("ctr_a", { x: 400, y: 330 }, { depth: 2, label: "Empty container" }),
    ];

    const result = rebuildGroupFrames(nodes, new Set(["ctr_a"]));

    expect(result.some((n) => n.id.startsWith("group-"))).toBe(false);
  });

  it("does not leave a stray header at the origin after rebuild", () => {
    const nodes = [
      flowNode("sys_1", { x: 400, y: 100 }, { depth: 1, label: "Kryptonite" }),
      flowNode("ctr_a", { x: 400, y: 330 }, { parentGroupId: "sys_1" }),
      flowNode("ctr_b", { x: 610, y: 330 }, { parentGroupId: "sys_1" }),
      flowNode("ctr_c", { x: 820, y: 330 }, { parentGroupId: "sys_1" }),
    ];

    const expanded = rebuildGroupFrames(nodes, new Set(["sys_1"]));
    const collapsed = rebuildGroupFrames(expanded, new Set());

    expect(collapsed.some((n) => n.id.startsWith("group-"))).toBe(false);

    const header = expanded.find((n) => n.id === "group-header-sys_1");
    expect(header?.position.x).toBeGreaterThan(300);
    expect(header?.position.y).toBeGreaterThan(200);
  });
});

import type { Node } from "@xyflow/react";
import { describe, expect, it } from "vitest";

import { layoutChildrenInGroup, calculateGroupFrame } from "./layout";

function flowNode(
  id: string,
  position: { x: number; y: number },
  data: Record<string, unknown> = {},
): Node {
  return { id, type: "expandable", position, data };
}

describe("layoutChildrenInGroup", () => {
  it("lays out every child in a grid below the parent", () => {
    const parent = flowNode("sys_1", { x: 400, y: 200 });
    const children = [
      flowNode("c1", { x: 0, y: 0 }, { parentGroupId: "sys_1" }),
      flowNode("c2", { x: 50, y: 40 }, { parentGroupId: "sys_1" }),
      flowNode("c3", { x: 900, y: 900 }, { parentGroupId: "sys_1" }),
    ];

    const positions = layoutChildrenInGroup(parent, children);

    expect(positions.get("c1")).toEqual({ x: 400, y: 330 });
    expect(positions.get("c2")).toEqual({ x: 610, y: 330 });
    // 3 children → 2 columns, third child wraps to row 2
    expect(positions.get("c3")).toEqual({ x: 400, y: 440 });
  });

  it("uses three columns for nine children", () => {
    const parent = flowNode("sys_1", { x: 100, y: 100 });
    const children = Array.from({ length: 9 }, (_, i) =>
      flowNode(`c${i}`, { x: 0, y: 0 }, { parentGroupId: "sys_1" }),
    );

    const positions = layoutChildrenInGroup(parent, children);
    const last = positions.get("c8");

    // row 2, col 2 in a 3-column grid below parent at y=100
    expect(last).toEqual({ x: 520, y: 450 });
  });
});

describe("calculateGroupFrame", () => {
  it("wraps all children at their live positions", () => {
    const parent = flowNode("sys_1", { x: 400, y: 100 });
    const children = [
      flowNode("c1", { x: 400, y: 330 }),
      flowNode("c2", { x: 610, y: 330 }),
      flowNode("c3", { x: 820, y: 330 }),
    ];

    const frame = calculateGroupFrame(parent, children);

    expect(frame.position.x).toBeGreaterThan(350);
    expect(frame.position.y).toBeGreaterThan(250);
    expect(frame.width).toBeGreaterThan(500);
    expect(frame.height).toBeGreaterThan(100);
  });

  it("does not create a tiny frame at the origin when one child has 0,0 coords", () => {
    const parent = flowNode("sys_1", { x: 400, y: 200 });
    const children = [
      flowNode("c1", { x: 0, y: 0 }),
      flowNode("c2", { x: 400, y: 330 }),
      flowNode("c3", { x: 610, y: 330 }),
    ];

    const frame = calculateGroupFrame(parent, children);

    expect(frame.position.x).toBe(-20);
    expect(frame.position.y).toBeLessThan(302);
    expect(frame.width).toBeGreaterThan(600);
  });
});

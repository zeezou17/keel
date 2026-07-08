import { describe, expect, it } from "vitest";
import type { Node } from "@xyflow/react";

import { applyNodeChangesWithChildFollow } from "./dragChildren";

function makeNode(
  id: string,
  x: number,
  y: number,
  parentGroupId?: string,
): Node {
  return {
    id,
    type: "expandable",
    position: { x, y },
    data: { parentGroupId },
  };
}

describe("applyNodeChangesWithChildFollow", () => {
  it("moves children when an expanded parent is dragged", () => {
    const nodes = [
      makeNode("sys_a", 100, 100),
      makeNode("ctr_api", 120, 250, "sys_a"),
      makeNode("ctr_worker", 360, 250, "sys_a"),
    ];

    const next = applyNodeChangesWithChildFollow(
      [
        {
          id: "sys_a",
          type: "position",
          position: { x: 200, y: 150 },
          dragging: true,
        },
      ],
      nodes,
      new Set(["sys_a"]),
    );

    expect(next.find((node) => node.id === "sys_a")?.position).toEqual({ x: 200, y: 150 });
    expect(next.find((node) => node.id === "ctr_api")?.position).toEqual({ x: 220, y: 300 });
    expect(next.find((node) => node.id === "ctr_worker")?.position).toEqual({ x: 460, y: 300 });
  });
});

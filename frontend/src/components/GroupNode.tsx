/**
 * Group node component for visually framing expanded children.
 *
 * When a system/container is expanded, its children are rendered inside
 * this group frame with a header showing the parent name.
 */
import { type NodeProps } from "@xyflow/react";

const DEPTH_COLORS: Record<number, { border: string; background: string; header: string }> = {
  1: {
    border: "#2a9d8f",
    background: "rgba(42, 157, 143, 0.05)",
    header: "#2a9d8f",
  },
  2: {
    border: "#457b9d",
    background: "rgba(69, 123, 157, 0.05)",
    header: "#457b9d",
  },
  3: {
    border: "#8d99ae",
    background: "rgba(141, 153, 174, 0.05)",
    header: "#8d99ae",
  },
};

export interface GroupNodeData {
  label: string;
  depth: number;
  childCount: number;
  onCollapse?: () => void;
}

export function GroupNode({ data }: NodeProps) {
  const { label, depth, childCount, onCollapse } = data as unknown as GroupNodeData;
  const colors = DEPTH_COLORS[depth] ?? DEPTH_COLORS[1];

  return (
    <div
      className="group-node"
      style={{
        border: `2px dashed ${colors.border}`,
        borderRadius: 12,
        background: colors.background,
        minWidth: 300,
        minHeight: 200,
        position: "relative",
      }}
    >
      <div
        className="group-node-header"
        style={{
          background: colors.header,
          color: "#ffffff",
          padding: "6px 12px",
          borderRadius: "10px 10px 0 0",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          fontSize: "0.85rem",
          fontWeight: 600,
        }}
      >
        <span>
          {label} <span style={{ opacity: 0.8, fontWeight: 400 }}>· C{depth + 1} · {childCount} children</span>
        </span>
        {onCollapse && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onCollapse();
            }}
            style={{
              border: 0,
              background: "rgba(255,255,255,0.2)",
              color: "white",
              borderRadius: 4,
              padding: "2px 8px",
              cursor: "pointer",
              fontSize: "0.75rem",
            }}
            title="Collapse"
          >
            ▼ Collapse
          </button>
        )}
      </div>
    </div>
  );
}

export const groupNodeTypes = {
  group: GroupNode,
};

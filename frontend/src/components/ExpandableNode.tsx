/**
 * Custom React Flow node with expand/collapse chevron control.
 *
 * Used for system and container nodes that can have children.
 * Shows chevron indicator when node has children, handles expand/collapse on click.
 */
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { NodeType } from "../api/client";

const NODE_COLORS: Record<NodeType, string> = {
  person: "#f4a261",
  system: "#2a9d8f",
  container: "#457b9d",
  component: "#8d99ae",
  external: "#e76f51",
};

const DEPTH_TINTS: Record<number, string> = {
  1: "#ffffff",
  2: "#f0f9f8",
  3: "#eef4fa",
};

export interface ExpandableNodeData {
  label: string;
  nodeType: NodeType;
  description: string;
  depth: number;
  isExpanded: boolean;
  hasChildren: boolean;
  isHighlighted: boolean;
  isSelected: boolean;
  onExpand?: () => void;
  onCollapse?: () => void;
}

export function ExpandableNode({ data }: NodeProps) {
  const {
    label,
    nodeType,
    depth,
    isExpanded,
    hasChildren,
    isHighlighted,
    isSelected,
    onExpand,
    onCollapse,
  } = data as unknown as ExpandableNodeData;

  const borderColor = isHighlighted || isSelected ? "#f9c74f" : NODE_COLORS[nodeType];
  const backgroundColor = isHighlighted || isSelected
    ? "#fff8e6"
    : DEPTH_TINTS[depth] ?? "#ffffff";

  const handleChevronClick = (event: React.MouseEvent) => {
    event.stopPropagation();
    if (isExpanded) {
      onCollapse?.();
    } else {
      onExpand?.();
    }
  };

  return (
    <div
      className="expandable-node"
      style={{
        border: `3px solid ${borderColor}`,
        borderRadius: 10,
        padding: "10px 12px",
        background: backgroundColor,
        width: 180,
        boxShadow: isHighlighted || isSelected
          ? "0 0 0 3px rgba(249, 199, 79, 0.35)"
          : undefined,
        position: "relative",
      }}
    >
      <Handle type="target" position={Position.Top} />

      <div className="expandable-node-header">
        {hasChildren ? (
          <button
            className="expandable-node-chevron"
            onClick={handleChevronClick}
            aria-label={isExpanded ? "Collapse" : "Expand"}
            title={isExpanded ? "Collapse" : "Expand"}
          >
            {isExpanded ? "▼" : "▶"}
          </button>
        ) : (
          <span className="expandable-node-chevron-placeholder" />
        )}
        <span className="expandable-node-label">{label}</span>
      </div>

      <div className="expandable-node-type">{nodeType}</div>

      {depth > 1 && (
        <div className="expandable-node-depth-indicator">
          C{depth}{isExpanded && hasChildren ? ` · ${isExpanded ? "expanded" : ""}` : ""}
        </div>
      )}

      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}

export const expandableNodeTypes = {
  expandable: ExpandableNode,
};

/**
 * Decide whether a node can be deleted without confirmation (structurally empty).
 */
import type { ArchitectureFile, KeelNode } from "../api/client";
import type { ExpansionState } from "./expansion";
import { getCachedArchitecture, getSystemContainers } from "./expansion";

export interface NodeEmptyContext {
  c1Architecture: ArchitectureFile | null;
  c2Architecture: ArchitectureFile | null;
  expansionState: ExpansionState;
}

export interface NodeNonemptyReason {
  kind: "edges" | "children" | "requirements" | "adrs" | "paths";
  count: number;
}

function countConnectedEdges(nodeId: string, architectures: ArchitectureFile[]): number {
  let count = 0;
  for (const architecture of architectures) {
    for (const edge of architecture.edges) {
      if (edge.source_id === nodeId || edge.target_id === nodeId) {
        count += 1;
      }
    }
  }
  return count;
}

function countChildNodes(
  node: KeelNode,
  c1Architecture: ArchitectureFile | null,
  c2Architecture: ArchitectureFile | null,
  expansionState: ExpansionState,
): number {
  if (node.type === "system") {
    return getSystemContainers(node.id, c2Architecture, c1Architecture).length;
  }

  if (node.type === "container") {
    const cached = getCachedArchitecture(expansionState, node.id);
    return cached?.nodes.length ?? 0;
  }

  return 0;
}

function architecturesForNode(
  node: KeelNode,
  context: NodeEmptyContext,
): ArchitectureFile[] {
  const files: ArchitectureFile[] = [];
  const { c1Architecture, c2Architecture, expansionState } = context;

  if (node.level === 1 && c1Architecture) {
    files.push(c1Architecture);
  }
  if (node.level === 2 && c2Architecture) {
    files.push(c2Architecture);
  }
  if (node.level === 3) {
    const parentId = node.parent_id;
    if (parentId) {
      const cached = getCachedArchitecture(expansionState, parentId);
      if (cached) {
        files.push(cached);
      }
    }
  }

  return files;
}

export function getNodeNonemptyReasons(
  node: KeelNode,
  context: NodeEmptyContext,
): NodeNonemptyReason[] {
  const reasons: NodeNonemptyReason[] = [];

  const edgeCount = countConnectedEdges(node.id, architecturesForNode(node, context));
  if (edgeCount > 0) {
    reasons.push({ kind: "edges", count: edgeCount });
  }

  const childCount = countChildNodes(
    node,
    context.c1Architecture,
    context.c2Architecture,
    context.expansionState,
  );
  if (childCount > 0) {
    reasons.push({ kind: "children", count: childCount });
  }

  const requirementCount = node.req_ids?.length ?? 0;
  if (requirementCount > 0) {
    reasons.push({ kind: "requirements", count: requirementCount });
  }

  const adrCount = node.adr_ids?.length ?? 0;
  if (adrCount > 0) {
    reasons.push({ kind: "adrs", count: adrCount });
  }

  const pathCount = node.paths?.length ?? 0;
  if (pathCount > 0) {
    reasons.push({ kind: "paths", count: pathCount });
  }

  return reasons;
}

export function isNodeEmpty(node: KeelNode, context: NodeEmptyContext): boolean {
  return getNodeNonemptyReasons(node, context).length === 0;
}

function formatReason(reason: NodeNonemptyReason): string {
  switch (reason.kind) {
    case "edges":
      return `${reason.count} connected edge${reason.count === 1 ? "" : "s"}`;
    case "children":
      return `${reason.count} child node${reason.count === 1 ? "" : "s"}`;
    case "requirements":
      return `${reason.count} linked requirement${reason.count === 1 ? "" : "s"}`;
    case "adrs":
      return `${reason.count} linked ADR${reason.count === 1 ? "" : "s"}`;
    case "paths":
      return `${reason.count} path glob${reason.count === 1 ? "" : "s"}`;
  }
}

export function buildDeleteConfirmMessage(
  node: KeelNode,
  reasons: NodeNonemptyReason[],
): string {
  const summary = reasons.map(formatReason).join(", ");
  return `Delete "${node.name}"? This node has ${summary}. This cannot be undone yet.`;
}

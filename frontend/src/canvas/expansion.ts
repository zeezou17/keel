/**
 * Expansion state management for selective drill-down (FP-003).
 *
 * Handles expand/collapse of C4 nodes, lazy-loading of child architecture,
 * caching, and composition of flat React Flow nodes from multiple architecture files.
 */
import type { ArchitectureFile, KeelNode, KeelEdge } from "../api/client";

const STORAGE_KEY = "keel:expansion-state";

export interface ExpansionState {
  expandedNodeIds: Set<string>;
  childArchitectureCache: Map<string, ArchitectureFile>;
}

export interface PersistedExpansionState {
  expandedNodeIds: string[];
}

export interface ComposedCanvas {
  nodes: ComposedNode[];
  edges: ComposedEdge[];
}

export interface ComposedNode extends KeelNode {
  depth: number;
  parentGroupId?: string | null;
  isExpanded: boolean;
  hasChildren: boolean;
}

export interface ComposedEdge extends KeelEdge {
  depth: number;
  groupId?: string | null;
}

export function createExpansionState(): ExpansionState {
  return {
    expandedNodeIds: new Set(),
    childArchitectureCache: new Map(),
  };
}

export function loadExpansionState(): ExpansionState {
  // On page refresh, start fresh with no expanded nodes.
  // The child architecture cache is not persisted, so restoring expanded IDs
  // without their children causes orphan nodes and visual glitches.
  // Users can re-expand nodes to restore their previous view.
  
  // Clear any stale localStorage data from previous versions
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Ignore storage errors
  }
  
  return createExpansionState();
}

export function saveExpansionState(_state: ExpansionState): void {
  // No-op: Expansion state is no longer persisted to localStorage.
  // The child architecture cache is not persisted, so restoring expanded IDs
  // without their children causes orphan nodes and visual glitches.
  // Users re-expand nodes when they return to the page.
}

export function isExpanded(state: ExpansionState, nodeId: string): boolean {
  return state.expandedNodeIds.has(nodeId);
}

export function toggleExpansion(
  state: ExpansionState,
  nodeId: string
): ExpansionState {
  const next = new Set(state.expandedNodeIds);
  if (next.has(nodeId)) {
    next.delete(nodeId);
  } else {
    next.add(nodeId);
  }
  return {
    ...state,
    expandedNodeIds: next,
  };
}

export function expandNode(
  state: ExpansionState,
  nodeId: string
): ExpansionState {
  if (state.expandedNodeIds.has(nodeId)) {
    return state;
  }
  const next = new Set(state.expandedNodeIds);
  next.add(nodeId);
  return {
    ...state,
    expandedNodeIds: next,
  };
}

export function collapseNode(
  state: ExpansionState,
  nodeId: string
): ExpansionState {
  if (!state.expandedNodeIds.has(nodeId)) {
    return state;
  }
  const next = new Set(state.expandedNodeIds);
  next.delete(nodeId);
  return {
    ...state,
    expandedNodeIds: next,
  };
}

export function collapseAll(state: ExpansionState): ExpansionState {
  return {
    ...state,
    expandedNodeIds: new Set(),
  };
}

export function expandMultiple(
  state: ExpansionState,
  nodeIds: string[]
): ExpansionState {
  const next = new Set(state.expandedNodeIds);
  for (const id of nodeIds) {
    next.add(id);
  }
  return {
    ...state,
    expandedNodeIds: next,
  };
}

export function cacheChildArchitecture(
  state: ExpansionState,
  nodeId: string,
  architecture: ArchitectureFile
): ExpansionState {
  const nextCache = new Map(state.childArchitectureCache);
  nextCache.set(nodeId, architecture);
  return {
    ...state,
    childArchitectureCache: nextCache,
  };
}

export function getCachedArchitecture(
  state: ExpansionState,
  nodeId: string
): ArchitectureFile | undefined {
  return state.childArchitectureCache.get(nodeId);
}

export function canNodeExpand(node: KeelNode): boolean {
  return node.type === "system" || node.type === "container";
}

/** For legacy C2 files without parent_id, pick the main C1 system by edge connectivity. */
export function getLegacyPrimarySystemId(c1Architecture: ArchitectureFile | null): string | null {
  if (!c1Architecture) return null;

  const systems = c1Architecture.nodes.filter((n) => n.type === "system");
  if (systems.length === 0) return null;
  if (systems.length === 1) return systems[0].id;

  const edgeCount = new Map<string, number>();
  for (const system of systems) {
    edgeCount.set(system.id, 0);
  }

  for (const edge of c1Architecture.edges) {
    if (edgeCount.has(edge.source_id)) {
      edgeCount.set(edge.source_id, (edgeCount.get(edge.source_id) ?? 0) + 1);
    }
    if (edgeCount.has(edge.target_id)) {
      edgeCount.set(edge.target_id, (edgeCount.get(edge.target_id) ?? 0) + 1);
    }
  }

  return systems.reduce((best, system) =>
    (edgeCount.get(system.id) ?? 0) > (edgeCount.get(best.id) ?? 0) ? system : best,
  ).id;
}

/** Legacy C2 containers with no parent_id — assigned to a system by C1 topology rules. */
export function getLegacyOrphanContainersForSystem(
  systemId: string,
  orphans: KeelNode[],
  c1Architecture: ArchitectureFile | null,
): KeelNode[] {
  if (orphans.length === 0) return [];

  const c1Systems = c1Architecture?.nodes.filter((n) => n.type === "system") ?? [];
  if (c1Systems.length === 1 && c1Systems[0].id === systemId) {
    return orphans;
  }

  const primarySystemId = getLegacyPrimarySystemId(c1Architecture);
  if (primarySystemId === systemId) {
    return orphans;
  }

  return [];
}

/** C2 containers that belong inline under an expanded system. */
export function getSystemContainers(
  systemId: string,
  c2Architecture: ArchitectureFile | null,
  c1Architecture: ArchitectureFile | null = null,
): KeelNode[] {
  if (!c2Architecture) return [];

  const c2Containers = c2Architecture.nodes.filter((n) => n.type === "container");
  if (c2Containers.length === 0) return [];

  const explicit = c2Containers.filter((n) => n.parent_id === systemId);
  const orphans = c2Containers.filter((n) => !n.parent_id);
  const legacyOrphans = getLegacyOrphanContainersForSystem(systemId, orphans, c1Architecture);

  const byId = new Map<string, KeelNode>();
  for (const container of [...explicit, ...legacyOrphans]) {
    byId.set(container.id, container);
  }
  return [...byId.values()];
}

/** Whether a node actually has child architecture to show when expanded. */
export function nodeHasExpandableChildren(
  node: KeelNode,
  state: ExpansionState,
  c2Architecture: ArchitectureFile | null,
  c1Architecture: ArchitectureFile | null = null,
): boolean {
  if (node.type === "system") {
    return getSystemContainers(node.id, c2Architecture, c1Architecture).length > 0;
  }
  if (node.type === "container") {
    const c3 = getCachedArchitecture(state, node.id);
    return (c3?.nodes.length ?? 0) > 0;
  }
  return false;
}

/** Collapse a node and any descendant expansions (e.g. containers inside a system). */
export function collapseSubtree(
  state: ExpansionState,
  node: KeelNode,
  c2Architecture: ArchitectureFile | null,
  c1Architecture: ArchitectureFile | null = null,
): ExpansionState {
  if (!state.expandedNodeIds.has(node.id)) {
    return state;
  }

  const next = new Set(state.expandedNodeIds);
  next.delete(node.id);

  if (node.type === "system" && c2Architecture) {
    for (const child of getSystemContainers(node.id, c2Architecture, c1Architecture)) {
      next.delete(child.id);
    }
  }

  return {
    ...state,
    expandedNodeIds: next,
  };
}

export function getChildLevel(node: KeelNode): number | null {
  if (node.type === "system") return 2;
  if (node.type === "container") return 3;
  return null;
}

/**
 * Compose a flat list of nodes from the root architecture + expanded children.
 *
 * This merges C1 nodes with any expanded C2/C3 children, marking each node
 * with its depth level and parent group for visual rendering.
 */
export function composeCanvas(
  rootArchitecture: ArchitectureFile,
  state: ExpansionState,
  c2Architecture: ArchitectureFile | null
): ComposedCanvas {
  const composedNodes: ComposedNode[] = [];
  const composedEdges: ComposedEdge[] = [];

  // Add root-level (C1) nodes
  for (const node of rootArchitecture.nodes) {
    const expanded = state.expandedNodeIds.has(node.id);
    const hasChildren = nodeHasExpandableChildren(node, state, c2Architecture, rootArchitecture);

    composedNodes.push({
      ...node,
      depth: 1,
      parentGroupId: null,
      isExpanded: expanded,
      hasChildren,
    });

    // If this node is expanded, add its children
    if (expanded && node.type === "system" && c2Architecture) {
      const systemContainers = getSystemContainers(node.id, c2Architecture, rootArchitecture);

      for (const child of systemContainers) {
        const childExpanded = state.expandedNodeIds.has(child.id);
        const hasChildChildren = nodeHasExpandableChildren(child, state, c2Architecture, rootArchitecture);

        composedNodes.push({
          ...child,
          depth: 2,
          parentGroupId: node.id,
          isExpanded: childExpanded,
          hasChildren: hasChildChildren,
        });

        // If container is expanded, add C3 components
        if (childExpanded) {
          const c3Architecture = getCachedArchitecture(state, child.id);
          if (c3Architecture) {
            for (const component of c3Architecture.nodes) {
              composedNodes.push({
                ...component,
                depth: 3,
                parentGroupId: child.id,
                isExpanded: false,
                hasChildren: false,
              });
            }
            // Add C3 edges
            for (const edge of c3Architecture.edges) {
              composedEdges.push({
                ...edge,
                depth: 3,
                groupId: child.id,
              });
            }
          }
        }
      }

      // Add C2-level edges (between containers in this system's group)
      for (const edge of c2Architecture.edges) {
        const sourceInGroup = systemContainers.some((c) => c.id === edge.source_id);
        const targetInGroup = systemContainers.some((c) => c.id === edge.target_id);
        if (sourceInGroup || targetInGroup) {
          composedEdges.push({
            ...edge,
            depth: 2,
            groupId: node.id,
          });
        }
      }
    }
  }

  // Add root-level (C1) edges
  for (const edge of rootArchitecture.edges) {
    composedEdges.push({
      ...edge,
      depth: 1,
      groupId: null,
    });
  }

  return { nodes: composedNodes, edges: composedEdges };
}

/**
 * Get the deepest expanded node or selected node for sparring context.
 */
export function getSparringContext(
  state: ExpansionState,
  selectedNode: KeelNode | null,
  _rootArchitecture: ArchitectureFile
): { level: number; containerId: string | null } {
  // If a node is selected, use its context
  if (selectedNode) {
    if (selectedNode.level === 3) {
      return { level: 3, containerId: selectedNode.parent_id ?? null };
    }
    if (selectedNode.level === 2 && state.expandedNodeIds.has(selectedNode.id)) {
      return { level: 3, containerId: selectedNode.id };
    }
    if (selectedNode.level === 2) {
      return { level: 2, containerId: null };
    }
    if (selectedNode.level === 1 && state.expandedNodeIds.has(selectedNode.id)) {
      return { level: 2, containerId: null };
    }
    return { level: 1, containerId: null };
  }

  // Find the deepest expanded node
  let deepestLevel = 1;
  let deepestContainerId: string | null = null;

  for (const nodeId of state.expandedNodeIds) {
    // Check if this is an expanded container (level 2)
    const c3Cache = getCachedArchitecture(state, nodeId);
    if (c3Cache) {
      if (deepestLevel < 3) {
        deepestLevel = 3;
        deepestContainerId = nodeId;
      }
    } else {
      // It's an expanded system
      if (deepestLevel < 2) {
        deepestLevel = 2;
        deepestContainerId = null;
      }
    }
  }

  return { level: deepestLevel, containerId: deepestContainerId };
}

/**
 * Get the focused context for Add Node operation.
 */
export interface AddNodeContext {
  level: number;
  containerId: string | null;
  parentId: string | null;
  focusName: string | null;
}

export function formatAddNodeLabel(context: AddNodeContext): string {
  if (context.level <= 1) {
    return "Add node";
  }
  if (context.focusName) {
    return `Add node (C${context.level} · ${context.focusName})`;
  }
  return `Add node (C${context.level})`;
}

function findNodeName(
  nodeId: string,
  c1Architecture: ArchitectureFile | null,
  c2Architecture: ArchitectureFile | null,
): string | null {
  const c1 = c1Architecture?.nodes.find((node) => node.id === nodeId);
  if (c1) return c1.name;
  const c2 = c2Architecture?.nodes.find((node) => node.id === nodeId);
  return c2?.name ?? null;
}

export function getAddNodeContext(
  state: ExpansionState,
  selectedNode: KeelNode | null,
  c1Architecture: ArchitectureFile | null = null,
  c2Architecture: ArchitectureFile | null = null,
): AddNodeContext {
  // If a node is selected, prefer its context over expanded-set iteration order.
  if (selectedNode) {
    if (selectedNode.type === "container") {
      return {
        level: 3,
        containerId: selectedNode.id,
        parentId: selectedNode.id,
        focusName: selectedNode.name,
      };
    }

    if (selectedNode.type === "system") {
      if (state.expandedNodeIds.has(selectedNode.id)) {
        return {
          level: 2,
          containerId: null,
          parentId: selectedNode.id,
          focusName: selectedNode.name,
        };
      }
      return {
        level: 1,
        containerId: null,
        parentId: null,
        focusName: selectedNode.name,
      };
    }

    if (selectedNode.type === "component") {
      const parentId = selectedNode.parent_id ?? null;
      return {
        level: 3,
        containerId: parentId,
        parentId,
        focusName: selectedNode.name,
      };
    }

    return {
      level: selectedNode.level,
      containerId: selectedNode.level === 3 ? selectedNode.parent_id ?? null : null,
      parentId: selectedNode.parent_id ?? null,
      focusName: selectedNode.name,
    };
  }

  // No selection — use the most recently expanded node (Set preserves insertion order).
  if (state.expandedNodeIds.size > 0) {
    const expandedIds = [...state.expandedNodeIds];
    const lastExpandedId = expandedIds[expandedIds.length - 1];

    const expandedSystem = c1Architecture?.nodes.find(
      (node) => node.id === lastExpandedId && node.type === "system",
    );
    if (expandedSystem) {
      return {
        level: 2,
        containerId: null,
        parentId: expandedSystem.id,
        focusName: expandedSystem.name,
      };
    }

    const expandedContainer = c2Architecture?.nodes.find(
      (node) => node.id === lastExpandedId && node.type === "container",
    );
    if (expandedContainer) {
      return {
        level: 3,
        containerId: expandedContainer.id,
        parentId: expandedContainer.id,
        focusName: expandedContainer.name,
      };
    }

    if (getCachedArchitecture(state, lastExpandedId)) {
      return {
        level: 3,
        containerId: lastExpandedId,
        parentId: lastExpandedId,
        focusName: findNodeName(lastExpandedId, c1Architecture, c2Architecture),
      };
    }
  }

  return { level: 1, containerId: null, parentId: null, focusName: null };
}

/**
 * Find ancestor nodes that need to be expanded to make a node visible.
 */
export function findAncestorsToExpand(
  nodeId: string,
  allNodes: KeelNode[],
  currentExpanded: Set<string>
): string[] {
  const ancestors: string[] = [];
  const nodeMap = new Map(allNodes.map((n) => [n.id, n]));

  let current = nodeMap.get(nodeId);
  while (current?.parent_id) {
    const parent = nodeMap.get(current.parent_id);
    if (parent && !currentExpanded.has(parent.id)) {
      ancestors.unshift(parent.id);
    }
    current = parent;
  }

  return ancestors;
}

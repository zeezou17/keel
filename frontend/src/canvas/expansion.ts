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
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return createExpansionState();
    }
    const parsed = JSON.parse(raw) as PersistedExpansionState;
    return {
      expandedNodeIds: new Set(parsed.expandedNodeIds ?? []),
      childArchitectureCache: new Map(),
    };
  } catch {
    return createExpansionState();
  }
}

export function saveExpansionState(state: ExpansionState): void {
  const persisted: PersistedExpansionState = {
    expandedNodeIds: Array.from(state.expandedNodeIds),
  };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(persisted));
  } catch {
    // Storage full or unavailable
  }
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
    const canExpand = canNodeExpand(node);

    composedNodes.push({
      ...node,
      depth: 1,
      parentGroupId: null,
      isExpanded: expanded,
      hasChildren: canExpand,
    });

    // If this node is expanded, add its children
    if (expanded && node.type === "system" && c2Architecture) {
      // Filter C2 containers that belong to this system
      // C2 nodes may have parent_id set to the system, or we show all containers
      // when expanding any system (current API returns all C2 containers)
      const systemContainers = c2Architecture.nodes.filter(
        (c2Node) => c2Node.parent_id === node.id || !c2Node.parent_id
      );

      for (const child of systemContainers) {
        const childExpanded = state.expandedNodeIds.has(child.id);
        const childCanExpand = canNodeExpand(child);

        composedNodes.push({
          ...child,
          depth: 2,
          parentGroupId: node.id,
          isExpanded: childExpanded,
          hasChildren: childCanExpand,
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
export function getAddNodeContext(
  state: ExpansionState,
  selectedNode: KeelNode | null
): { level: number; containerId: string | null } {
  // If a node is selected
  if (selectedNode) {
    // If it's a container and expanded, add at C3 level
    if (selectedNode.type === "container" && state.expandedNodeIds.has(selectedNode.id)) {
      return { level: 3, containerId: selectedNode.id };
    }
    // If it's a system and expanded, add at C2 level
    if (selectedNode.type === "system" && state.expandedNodeIds.has(selectedNode.id)) {
      return { level: 2, containerId: null };
    }
    // Otherwise add at the same level as selected node
    return {
      level: selectedNode.level,
      containerId: selectedNode.level === 3 ? selectedNode.parent_id ?? null : null,
    };
  }

  // No selection - check for expanded nodes
  for (const nodeId of state.expandedNodeIds) {
    const c3Cache = getCachedArchitecture(state, nodeId);
    if (c3Cache) {
      return { level: 3, containerId: nodeId };
    }
  }

  // Check for any expanded systems
  if (state.expandedNodeIds.size > 0) {
    return { level: 2, containerId: null };
  }

  // Default to C1
  return { level: 1, containerId: null };
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

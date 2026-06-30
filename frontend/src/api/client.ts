export type NodeType = "person" | "system" | "container" | "component" | "external";

export interface KeelNode {
  id: string;
  type: NodeType;
  level: number;
  name: string;
  description: string;
  paths: string[];
  parent_id?: string | null;
  technology?: string | null;
  position_x?: number | null;
  position_y?: number | null;
}

export interface KeelEdge {
  id: string;
  type: string;
  source_id: string;
  target_id: string;
  label?: string | null;
}

export interface ArchitectureFile {
  schema_version: number;
  level: number;
  container_id?: string | null;
  nodes: KeelNode[];
  edges: KeelEdge[];
}

export interface GitStatus {
  dirty: boolean;
  changed_files: string[];
}

export interface SparAction {
  type: "add_node";
  label: string;
  level: number;
  container_id?: string | null;
  node: KeelNode;
}

export interface SparResult {
  reply: string;
  actions: SparAction[];
}

export interface SparMessage {
  id: string;
  role: "user" | "assistant" | "error";
  content: string;
  actions?: SparAction[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    const raw = await response.text();
    try {
      const payload = JSON.parse(raw) as { detail?: string };
      if (typeof payload.detail === "string") {
        throw new Error(payload.detail);
      }
    } catch (error) {
      if (error instanceof Error && error.message !== raw) {
        throw error;
      }
    }
    throw new Error(raw || response.statusText);
  }
  return response.json() as Promise<T>;
}

export function fetchArchitecture(level: number, containerId?: string | null) {
  const query = containerId ? `?container_id=${encodeURIComponent(containerId)}` : "";
  return request<ArchitectureFile>(`/api/architecture/${level}${query}`);
}

export function saveArchitecture(
  level: number,
  body: ArchitectureFile,
  containerId?: string | null,
) {
  const query = containerId ? `?container_id=${encodeURIComponent(containerId)}` : "";
  return request<ArchitectureFile>(`/api/architecture/${level}${query}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function createNode(level: number, node: KeelNode, containerId?: string | null) {
  return request<ArchitectureFile>("/api/architecture/node", {
    method: "POST",
    body: JSON.stringify({ level, container_id: containerId ?? null, node }),
  });
}

export function updateNode(nodeId: string, node: KeelNode) {
  return request<ArchitectureFile>(`/api/architecture/node/${encodeURIComponent(nodeId)}`, {
    method: "PUT",
    body: JSON.stringify(node),
  });
}

export function fetchGitStatus() {
  return request<GitStatus>("/api/git/status");
}

export function commitChanges(message = "chore: update keel architecture") {
  return request<{ commit: string }>("/api/commit", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export function spar(message: string, level: number, containerId?: string | null) {
  return request<SparResult>("/api/spar", {
    method: "POST",
    body: JSON.stringify({
      message,
      level,
      container_id: containerId ?? null,
    }),
  });
}

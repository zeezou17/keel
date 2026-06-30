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

export type ReqStatus = "draft" | "approved" | "implemented";
export type ADRStatus = "proposed" | "accepted" | "deprecated" | "superseded";
export type Priority = "high" | "medium" | "low";

export interface Requirement {
  id: string;
  title: string;
  status: ReqStatus;
  linked_node_ids: string[];
  acceptance_criteria: string[];
  body: string;
}

export interface ADR {
  id: string;
  title: string;
  status: ADRStatus;
  linked_node_ids: string[];
  linked_characteristic_ids: string[];
  body: string;
}

export interface Characteristic {
  id: string;
  name: string;
  priority: Priority;
  scenario: string;
  fitness_function?: { type: string; ref: string } | null;
  linked_node_ids: string[];
}

export interface ImpactItem {
  node_id: string;
  reason: string;
}

export interface AssessImpactResult {
  impacts: ImpactItem[];
}

export function fetchNodes() {
  return request<KeelNode[]>("/api/nodes");
}

export function fetchRequirements() {
  return request<Requirement[]>("/api/requirements");
}

export function createRequirement(title: string, description = "") {
  return request<Requirement>("/api/requirements", {
    method: "POST",
    body: JSON.stringify({ title, description }),
  });
}

export function updateRequirement(requirement: Requirement) {
  return request<Requirement>(`/api/requirements/${encodeURIComponent(requirement.id)}`, {
    method: "PUT",
    body: JSON.stringify({
      title: requirement.title,
      status: requirement.status,
      linked_node_ids: requirement.linked_node_ids,
      acceptance_criteria: requirement.acceptance_criteria,
      body: requirement.body,
    }),
  });
}

export function assessImpact(requirementId: string) {
  return request<AssessImpactResult>("/api/assess-impact", {
    method: "POST",
    body: JSON.stringify({ requirement_id: requirementId }),
  });
}

export function fetchAdrs() {
  return request<ADR[]>("/api/adrs");
}

export function createAdr(title: string) {
  return request<ADR>("/api/adrs", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
}

export function updateAdr(adr: ADR) {
  return request<ADR>(`/api/adrs/${encodeURIComponent(adr.id)}`, {
    method: "PUT",
    body: JSON.stringify({
      title: adr.title,
      status: adr.status,
      linked_node_ids: adr.linked_node_ids,
      linked_characteristic_ids: adr.linked_characteristic_ids,
      body: adr.body,
    }),
  });
}

export function fetchCharacteristics() {
  return request<Characteristic[]>("/api/characteristics");
}

export function createCharacteristic(
  characteristic: Omit<Characteristic, "id">,
) {
  return request<Characteristic>("/api/characteristics", {
    method: "POST",
    body: JSON.stringify(characteristic),
  });
}

export function updateCharacteristic(characteristic: Characteristic) {
  return request<Characteristic>(`/api/characteristics/${encodeURIComponent(characteristic.id)}`, {
    method: "PUT",
    body: JSON.stringify(characteristic),
  });
}

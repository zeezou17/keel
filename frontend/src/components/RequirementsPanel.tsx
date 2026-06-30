import { useEffect, useState } from "react";

import {
  assessImpact,
  createRequirement,
  fetchNodes,
  fetchRequirements,
  updateRequirement,
  type ImpactItem,
  type KeelNode,
  type Requirement,
} from "../api/client";

interface RequirementsPanelProps {
  selectedId: string | null;
  onSelect: (requirement: Requirement | null, highlightedNodeIds: string[]) => void;
  onArchitectureRefresh: () => void;
}

export function RequirementsPanel({
  selectedId,
  onSelect,
  onArchitectureRefresh,
}: RequirementsPanelProps) {
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [nodes, setNodes] = useState<KeelNode[]>([]);
  const [impacts, setImpacts] = useState<ImpactItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selected = requirements.find((item) => item.id === selectedId) ?? null;

  const load = async () => {
    const [reqs, nodeList] = await Promise.all([fetchRequirements(), fetchNodes()]);
    setRequirements(reqs);
    setNodes(nodeList);
  };

  useEffect(() => {
    void load();
  }, []);

  const handleCreate = async () => {
    const created = await createRequirement("New requirement", "Describe the requirement.");
    setRequirements((current) => [...current, created]);
    onSelect(created, created.linked_node_ids);
  };

  const handleSave = async () => {
    if (!selected) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const saved = await updateRequirement(selected);
      setRequirements((current) => current.map((item) => (item.id === saved.id ? saved : item)));
      onSelect(saved, [...saved.linked_node_ids, ...impacts.map((item) => item.node_id)]);
      onArchitectureRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save requirement.");
    } finally {
      setLoading(false);
    }
  };

  const handleAssess = async () => {
    if (!selected) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await assessImpact(selected.id);
      setImpacts(result.impacts);
      const highlightIds = [...new Set(result.impacts.map((item) => item.node_id))];
      onSelect(selected, highlightIds);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impact assessment failed.");
    } finally {
      setLoading(false);
    }
  };

  const toggleNodeLink = (nodeId: string) => {
    if (!selected) {
      return;
    }
    const linked = new Set(selected.linked_node_ids);
    if (linked.has(nodeId)) {
      linked.delete(nodeId);
    } else {
      linked.add(nodeId);
    }
    const updated = { ...selected, linked_node_ids: [...linked] };
    setRequirements((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    onSelect(updated, [...linked]);
  };

  return (
    <div className="sidebar-panel">
      <div className="sidebar-panel-header">
        <h3>Requirements</h3>
        <button onClick={() => void handleCreate()}>New</button>
      </div>
      <ul className="sidebar-list">
        {requirements.map((item) => (
          <li key={item.id}>
            <button
              className={item.id === selectedId ? "active" : ""}
              onClick={() => {
                setImpacts([]);
                onSelect(item, item.linked_node_ids);
              }}
            >
              {item.id}: {item.title}
            </button>
          </li>
        ))}
      </ul>
      {selected ? (
        <div className="sidebar-detail">
          <label>
            Title
            <input
              value={selected.title}
              onChange={(event) => {
                const updated = { ...selected, title: event.target.value };
                setRequirements((current) =>
                  current.map((item) => (item.id === updated.id ? updated : item)),
                );
                onSelect(updated, updated.linked_node_ids);
              }}
            />
          </label>
          <label>
            Status
            <select
              value={selected.status}
              onChange={(event) => {
                const updated = { ...selected, status: event.target.value as Requirement["status"] };
                setRequirements((current) =>
                  current.map((item) => (item.id === updated.id ? updated : item)),
                );
                onSelect(updated, updated.linked_node_ids);
              }}
            >
              <option value="draft">draft</option>
              <option value="approved">approved</option>
              <option value="implemented">implemented</option>
            </select>
          </label>
          <label>
            Description
            <textarea
              value={selected.body}
              onChange={(event) => {
                const updated = { ...selected, body: event.target.value };
                setRequirements((current) =>
                  current.map((item) => (item.id === updated.id ? updated : item)),
                );
                onSelect(updated, updated.linked_node_ids);
              }}
            />
          </label>
          <div className="linked-nodes">
            <strong>Linked nodes</strong>
            {nodes.map((node) => (
              <label key={node.id} className="checkbox-row">
                <input
                  type="checkbox"
                  checked={selected.linked_node_ids.includes(node.id)}
                  onChange={() => toggleNodeLink(node.id)}
                />
                {node.name}
              </label>
            ))}
          </div>
          {impacts.length > 0 ? (
            <div className="impact-results">
              <strong>Impact assessment</strong>
              <ul>
                {impacts.map((impact) => (
                  <li key={impact.node_id}>
                    <code>{impact.node_id}</code>: {impact.reason}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {error ? <div className="panel-error">{error}</div> : null}
          <div className="sidebar-actions">
            <button onClick={() => void handleSave()} disabled={loading}>
              Save
            </button>
            <button onClick={() => void handleAssess()} disabled={loading}>
              Assess impact
            </button>
          </div>
        </div>
      ) : (
        <p className="sidebar-empty">Select or create a requirement.</p>
      )}
    </div>
  );
}

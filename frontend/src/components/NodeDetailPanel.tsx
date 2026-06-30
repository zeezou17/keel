import { useState } from "react";

import { generateWorkPackage, type KeelNode } from "../api/client";

interface NodeDetailPanelProps {
  node: KeelNode | null;
  canDrillDown: boolean;
  onDrillDown: (node: KeelNode) => void;
  onClose: () => void;
  onGenerated: () => void;
}

export function NodeDetailPanel({
  node,
  canDrillDown,
  onDrillDown,
  onClose,
  onGenerated,
}: NodeDetailPanelProps) {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!node) {
    return null;
  }

  const linkedRequirements = node.req_ids ?? [];

  const handleGenerate = async () => {
    if (linkedRequirements.length === 0) {
      setError(
        "This node has no linked requirements. Link at least one requirement in the sidebar before generating a work package.",
      );
      return;
    }

    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await generateWorkPackage(node.id, linkedRequirements);
      setMessage(`Created ${result.work_package.id} at ${result.path}`);
      onGenerated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Work package generation failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="node-detail-panel">
      <div className="node-detail-header">
        <strong>{node.name}</strong>
        <button onClick={onClose}>Close</button>
      </div>
      <p className="node-detail-meta">
        <code>{node.id}</code> · {node.type}
      </p>
      <p>{node.description}</p>
      <div className="node-detail-section">
        <strong>Linked requirements</strong>
        {linkedRequirements.length > 0 ? (
          <ul>
            {linkedRequirements.map((reqId) => (
              <li key={reqId}>{reqId}</li>
            ))}
          </ul>
        ) : (
          <p className="node-detail-warning">No linked requirements yet.</p>
        )}
      </div>
      {error ? <div className="panel-error">{error}</div> : null}
      {message ? <div className="node-detail-success">{message}</div> : null}
      <div className="node-detail-actions">
        {canDrillDown ? (
          <button onClick={() => onDrillDown(node)}>Drill down</button>
        ) : null}
        <button onClick={() => void handleGenerate()} disabled={loading}>
          {loading ? "Generating…" : "Generate work package"}
        </button>
      </div>
    </div>
  );
}

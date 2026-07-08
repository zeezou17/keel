/**
 * Floating panel when a diagram edge is selected.
 * Edit relationship label or delete the edge (FP-002).
 */
import { useEffect, useRef, useState } from "react";

import type { KeelEdge } from "../api/client";

interface EdgeDetailPanelProps {
  edge: KeelEdge | null;
  onSave: (edge: KeelEdge, label: string) => Promise<void>;
  onDelete: (edge: KeelEdge) => Promise<void>;
  onClose: () => void;
}

export function EdgeDetailPanel({ edge, onSave, onDelete, onClose }: EdgeDetailPanelProps) {
  const [label, setLabel] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const edgeIdRef = useRef<string | null>(edge?.id ?? null);

  useEffect(() => {
    edgeIdRef.current = edge?.id ?? null;
    setLabel(edge?.label ?? edge?.type ?? "");
    setError(null);
    setSaving(false);
    setDeleting(false);
  }, [edge?.id, edge?.label, edge?.type]);

  if (!edge) {
    return null;
  }

  const handleSave = async () => {
    const requestEdgeId = edge.id;
    setSaving(true);
    setError(null);
    try {
      await onSave(edge, label);
    } catch (err) {
      if (edgeIdRef.current !== requestEdgeId) return;
      setError(err instanceof Error ? err.message : "Failed to save edge.");
    } finally {
      if (edgeIdRef.current === requestEdgeId) {
        setSaving(false);
      }
    }
  };

  const handleDelete = async () => {
    const confirmed = window.confirm(
      `Delete the "${edge.label ?? edge.type}" link between ${edge.source_id} and ${edge.target_id}?`,
    );
    if (!confirmed) {
      return;
    }

    const requestEdgeId = edge.id;
    setDeleting(true);
    setError(null);
    try {
      await onDelete(edge);
    } catch (err) {
      if (edgeIdRef.current !== requestEdgeId) return;
      setError(err instanceof Error ? err.message : "Failed to delete edge.");
    } finally {
      if (edgeIdRef.current === requestEdgeId) {
        setDeleting(false);
      }
    }
  };

  return (
    <div className="edge-detail-panel">
      <div className="node-detail-header">
        <strong>Relationship</strong>
        <button type="button" onClick={(event) => { event.stopPropagation(); onClose(); }}>
          Close
        </button>
      </div>
      <p className="node-detail-meta">
        <code>{edge.id}</code> · {edge.type}
      </p>
      <p className="node-detail-meta">
        <code>{edge.source_id}</code> → <code>{edge.target_id}</code>
      </p>
      <label className="node-detail-field">
        <span>Label</span>
        <input
          type="text"
          value={label}
          onChange={(event) => setLabel(event.target.value)}
          disabled={saving || deleting}
        />
      </label>
      {error ? <div className="panel-error">{error}</div> : null}
      <div className="node-detail-actions">
        <button
          type="button"
          className="node-detail-delete-button"
          onClick={() => void handleDelete()}
          disabled={saving || deleting}
        >
          {deleting ? "Deleting…" : "Delete link"}
        </button>
        <button type="button" onClick={() => void handleSave()} disabled={saving || deleting}>
          {saving ? "Saving…" : "Save"}
        </button>
      </div>
    </div>
  );
}

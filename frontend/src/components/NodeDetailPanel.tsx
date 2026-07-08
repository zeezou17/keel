/**
 * Floating panel when a diagram node is selected.
 * Shows metadata, expand/collapse controls, edit fields, delete, and work package generation.
 *
 * FP-003: Replaced "Drill down" with Expand/Collapse for selective drill-down.
 * FP-008: Delete node — empty nodes delete immediately; others require confirmation.
 * FP-002: Editable node fields with explicit Save.
 */
import { useEffect, useMemo, useRef, useState } from "react";

import { generateWorkPackage, type KeelNode } from "../api/client";
import type { NodeEmptyContext } from "../canvas/nodeEmpty";
import {
  buildDeleteConfirmMessage,
  getNodeNonemptyReasons,
  isNodeEmpty,
} from "../canvas/nodeEmpty";

interface NodeDetailPanelProps {
  node: KeelNode | null;
  isExpanded: boolean;
  canExpand: boolean;
  emptyContext: NodeEmptyContext;
  onExpand: (node: KeelNode) => void;
  onCollapse: (node: KeelNode) => void;
  onSave: (node: KeelNode) => Promise<void>;
  onDelete: (node: KeelNode) => Promise<void>;
  onClose: () => void;
  onGenerated: () => void;
}

function pathsToText(paths: string[]): string {
  return paths.join("\n");
}

function textToPaths(value: string): string[] {
  return value
    .split(/[\n,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function NodeDetailPanel({
  node,
  isExpanded,
  canExpand,
  emptyContext,
  onExpand,
  onCollapse,
  onSave,
  onDelete,
  onClose,
  onGenerated,
}: NodeDetailPanelProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [technology, setTechnology] = useState("");
  const [pathsText, setPathsText] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const nodeIdRef = useRef<string | null>(node?.id ?? null);

  useEffect(() => {
    nodeIdRef.current = node?.id ?? null;
    setName(node?.name ?? "");
    setDescription(node?.description ?? "");
    setTechnology(node?.technology ?? "");
    setPathsText(pathsToText(node?.paths ?? []));
    setError(null);
    setMessage(null);
    setLoading(false);
    setSaving(false);
    setDeleting(false);
  }, [node?.id, node?.name, node?.description, node?.technology, node?.paths]);

  const empty = useMemo(
    () => (node ? isNodeEmpty(node, emptyContext) : true),
    [node, emptyContext],
  );

  if (!node) {
    return null;
  }

  const linkedRequirements = node.req_ids ?? [];
  const isDirty =
    name !== node.name ||
    description !== node.description ||
    (technology || "") !== (node.technology ?? "") ||
    pathsText !== pathsToText(node.paths ?? []);

  const handleSave = async () => {
    const trimmedName = name.trim();
    if (!trimmedName) {
      setError("Name is required.");
      return;
    }

    const requestNodeId = node.id;
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      await onSave({
        ...node,
        name: trimmedName,
        description: description.trim(),
        technology: technology.trim() || null,
        paths: textToPaths(pathsText),
      });
      if (nodeIdRef.current !== requestNodeId) return;
      setMessage("Node saved.");
    } catch (err) {
      if (nodeIdRef.current !== requestNodeId) return;
      setError(err instanceof Error ? err.message : "Failed to save node.");
    } finally {
      if (nodeIdRef.current === requestNodeId) {
        setSaving(false);
      }
    }
  };

  const handleGenerate = async () => {
    if (linkedRequirements.length === 0) {
      setError(
        "This node has no linked requirements. Link at least one requirement in the sidebar before generating a work package.",
      );
      return;
    }

    const requestNodeId = node.id;
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await generateWorkPackage(requestNodeId, linkedRequirements);
      if (nodeIdRef.current !== requestNodeId) return;
      setMessage(`Created ${result.work_package.id} at ${result.path}`);
      onGenerated();
    } catch (err) {
      if (nodeIdRef.current !== requestNodeId) return;
      setError(err instanceof Error ? err.message : "Work package generation failed.");
    } finally {
      if (nodeIdRef.current === requestNodeId) {
        setLoading(false);
      }
    }
  };

  const handleExpandCollapse = () => {
    if (isExpanded) {
      onCollapse(node);
    } else {
      onExpand(node);
    }
  };

  const handleDelete = async () => {
    if (deleting) {
      return;
    }

    if (!empty) {
      const reasons = getNodeNonemptyReasons(node, emptyContext);
      const confirmed = window.confirm(buildDeleteConfirmMessage(node, reasons));
      if (!confirmed) {
        return;
      }
    }

    const requestNodeId = node.id;
    setDeleting(true);
    setError(null);
    setMessage(null);
    try {
      await onDelete(node);
    } catch (err) {
      if (nodeIdRef.current !== requestNodeId) return;
      setError(err instanceof Error ? err.message : "Failed to delete node.");
    } finally {
      if (nodeIdRef.current === requestNodeId) {
        setDeleting(false);
      }
    }
  };

  const childLevelLabel = node.type === "system" ? "containers" : "components";

  return (
    <div className="node-detail-panel">
      <div className="node-detail-header">
        <strong>{node.name}</strong>
        <button type="button" onClick={(event) => { event.stopPropagation(); onClose(); }}>Close</button>
      </div>
      <p className="node-detail-meta">
        <code>{node.id}</code> · {node.type}
        {node.level > 1 && (
          <span style={{ marginLeft: "0.5rem", color: "#829ab1" }}>
            · C{node.level}
          </span>
        )}
      </p>

      <label className="node-detail-field">
        <span>Name</span>
        <input
          type="text"
          value={name}
          onChange={(event) => setName(event.target.value)}
          disabled={saving || deleting || loading}
        />
      </label>
      <label className="node-detail-field">
        <span>Description</span>
        <textarea
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          rows={3}
          disabled={saving || deleting || loading}
        />
      </label>
      <label className="node-detail-field">
        <span>Technology</span>
        <input
          type="text"
          value={technology}
          onChange={(event) => setTechnology(event.target.value)}
          placeholder="e.g. Python, PostgreSQL"
          disabled={saving || deleting || loading}
        />
      </label>
      <label className="node-detail-field">
        <span>Path globs</span>
        <textarea
          value={pathsText}
          onChange={(event) => setPathsText(event.target.value)}
          rows={3}
          placeholder={"src/api/**\nservices/billing/**"}
          disabled={saving || deleting || loading}
        />
      </label>

      {canExpand && (
        <div className="node-detail-expand-section">
          <button
            className={`node-detail-expand-button ${isExpanded ? "expanded" : ""}`}
            onClick={handleExpandCollapse}
          >
            {isExpanded ? "▼" : "▶"}{" "}
            {isExpanded ? `Collapse ${childLevelLabel}` : `Expand ${childLevelLabel}`}
          </button>
          {!isExpanded && (
            <span className="node-detail-expand-hint">
              Show {childLevelLabel} inside this {node.type}
            </span>
          )}
        </div>
      )}

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
        <button
          type="button"
          className="node-detail-delete-button"
          onClick={() => void handleDelete()}
          disabled={deleting || loading || saving}
          title={empty ? "Delete this empty node" : "Delete node (confirmation required)"}
        >
          {deleting ? "Deleting…" : "Delete"}
        </button>
        <button
          type="button"
          onClick={() => void handleSave()}
          disabled={!isDirty || saving || deleting || loading}
        >
          {saving ? "Saving…" : "Save"}
        </button>
        <button onClick={() => void handleGenerate()} disabled={loading || deleting || saving}>
          {loading ? "Generating…" : "Generate work package"}
        </button>
      </div>
    </div>
  );
}

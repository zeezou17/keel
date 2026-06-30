import { useEffect, useState } from "react";

import { createAdr, fetchAdrs, updateAdr, type ADR } from "../api/client";

export function ADRsPanel() {
  const [adrs, setAdrs] = useState<ADR[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selected = adrs.find((item) => item.id === selectedId) ?? null;

  useEffect(() => {
    void fetchAdrs().then(setAdrs);
  }, []);

  const handleCreate = async () => {
    const created = await createAdr("New architecture decision");
    setAdrs((current) => [...current, created]);
    setSelectedId(created.id);
  };

  const handleSave = async () => {
    if (!selected) {
      return;
    }
    setError(null);
    try {
      const saved = await updateAdr(selected);
      setAdrs((current) => current.map((item) => (item.id === saved.id ? saved : item)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save ADR.");
    }
  };

  return (
    <div className="sidebar-panel">
      <div className="sidebar-panel-header">
        <h3>ADRs</h3>
        <button onClick={() => void handleCreate()}>New</button>
      </div>
      <ul className="sidebar-list">
        {adrs.map((item) => (
          <li key={item.id}>
            <button
              className={item.id === selectedId ? "active" : ""}
              onClick={() => setSelectedId(item.id)}
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
                setAdrs((current) => current.map((item) => (item.id === updated.id ? updated : item)));
              }}
            />
          </label>
          <label>
            Status
            <select
              value={selected.status}
              onChange={(event) => {
                const updated = { ...selected, status: event.target.value as ADR["status"] };
                setAdrs((current) => current.map((item) => (item.id === updated.id ? updated : item)));
              }}
            >
              <option value="proposed">proposed</option>
              <option value="accepted">accepted</option>
              <option value="deprecated">deprecated</option>
              <option value="superseded">superseded</option>
            </select>
          </label>
          <label>
            Body
            <textarea
              value={selected.body}
              onChange={(event) => {
                const updated = { ...selected, body: event.target.value };
                setAdrs((current) => current.map((item) => (item.id === updated.id ? updated : item)));
              }}
            />
          </label>
          {error ? <div className="panel-error">{error}</div> : null}
          <div className="sidebar-actions">
            <button onClick={() => void handleSave()}>Save</button>
          </div>
        </div>
      ) : (
        <p className="sidebar-empty">Select or create an ADR.</p>
      )}
    </div>
  );
}

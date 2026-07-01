/**
 * Quality characteristics (non-functional requirements) in the left sidebar.
 */
import { useEffect, useState } from "react";

import {
  createCharacteristic,
  fetchCharacteristics,
  updateCharacteristic,
  type Characteristic,
  type Priority,
} from "../api/client";

export function CharacteristicsPanel() {
  const [items, setItems] = useState<Characteristic[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selected = items.find((item) => item.id === selectedId) ?? null;

  useEffect(() => {
    void fetchCharacteristics().then(setItems);
  }, []);

  const handleCreate = async () => {
    const created = await createCharacteristic({
      name: "New characteristic",
      priority: "medium",
      scenario: "Define a measurable scenario.",
      linked_node_ids: [],
    });
    setItems((current) => [...current, created]);
    setSelectedId(created.id);
  };

  const handleSave = async () => {
    if (!selected) {
      return;
    }
    setError(null);
    try {
      const saved = await updateCharacteristic(selected);
      setItems((current) => current.map((item) => (item.id === saved.id ? saved : item)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save characteristic.");
    }
  };

  return (
    <div className="sidebar-panel">
      <div className="sidebar-panel-header">
        <h3>Characteristics</h3>
        <button onClick={() => void handleCreate()}>New</button>
      </div>
      <ul className="sidebar-list">
        {items.map((item) => (
          <li key={item.id}>
            <button
              className={item.id === selectedId ? "active" : ""}
              onClick={() => setSelectedId(item.id)}
            >
              {item.id}: {item.name}
            </button>
          </li>
        ))}
      </ul>
      {selected ? (
        <div className="sidebar-detail">
          <label>
            Name
            <input
              value={selected.name}
              onChange={(event) => {
                const updated = { ...selected, name: event.target.value };
                setItems((current) => current.map((item) => (item.id === updated.id ? updated : item)));
              }}
            />
          </label>
          <label>
            Priority
            <select
              value={selected.priority}
              onChange={(event) => {
                const updated = { ...selected, priority: event.target.value as Priority };
                setItems((current) => current.map((item) => (item.id === updated.id ? updated : item)));
              }}
            >
              <option value="high">high</option>
              <option value="medium">medium</option>
              <option value="low">low</option>
            </select>
          </label>
          <label>
            Scenario
            <textarea
              value={selected.scenario}
              onChange={(event) => {
                const updated = { ...selected, scenario: event.target.value };
                setItems((current) => current.map((item) => (item.id === updated.id ? updated : item)));
              }}
            />
          </label>
          {error ? <div className="panel-error">{error}</div> : null}
          <div className="sidebar-actions">
            <button onClick={() => void handleSave()}>Save</button>
          </div>
        </div>
      ) : (
        <p className="sidebar-empty">Select or create a characteristic.</p>
      )}
    </div>
  );
}

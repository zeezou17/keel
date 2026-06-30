import { useState } from "react";

import {
  createNode,
  spar,
  type ArchitectureFile,
  type KeelNode,
  type SparAction,
  type SparMessage,
} from "../api/client";

interface SparringPanelProps {
  level: number;
  containerId?: string | null;
  collapsed: boolean;
  onToggleCollapsed: () => void;
  onArchitectureUpdated: (architecture: ArchitectureFile) => void;
}

export function SparringPanel({
  level,
  containerId,
  collapsed,
  onToggleCollapsed,
  onArchitectureUpdated,
}: SparringPanelProps) {
  const [messages, setMessages] = useState<SparMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const sendMessage = async () => {
    const trimmed = input.trim();
    if (!trimmed || loading) {
      return;
    }

    const userMessage: SparMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmed,
    };
    setMessages((current) => [...current, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const response = await spar(trimmed, level, containerId);
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: response.reply,
          actions: response.actions,
        },
      ]);
    } catch (err) {
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "error",
          content: err instanceof Error ? err.message : "Claude Code request failed.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const applyAction = async (action: SparAction) => {
    if (action.type !== "add_node") {
      return;
    }
    try {
      const updated = await createNode(action.level, action.node as KeelNode, action.container_id);
      if (action.level === level && (action.container_id ?? null) === (containerId ?? null)) {
        onArchitectureUpdated(updated);
      }
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: `Applied: ${action.label}`,
        },
      ]);
    } catch (err) {
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "error",
          content: err instanceof Error ? err.message : "Failed to apply suggestion.",
        },
      ]);
    }
  };

  if (collapsed) {
    return (
      <aside className="spar-panel collapsed">
        <button className="spar-toggle" onClick={onToggleCollapsed}>
          AI Sparring
        </button>
      </aside>
    );
  }

  return (
    <aside className="spar-panel">
      <div className="spar-header">
        <h2>AI Sparring</h2>
        <button className="spar-toggle" onClick={onToggleCollapsed}>
          Collapse
        </button>
      </div>
      <div className="spar-messages">
        {messages.length === 0 ? (
          <p className="spar-empty">Ask about architecture trade-offs, missing containers, or drift risks.</p>
        ) : null}
        {messages.map((message) => (
          <div key={message.id} className={`spar-message ${message.role}`}>
            <p>{message.content}</p>
            {message.actions?.map((action) => (
              <button
                key={`${message.id}-${action.label}`}
                className="spar-action"
                onClick={() => void applyAction(action)}
              >
                {action.label}
              </button>
            ))}
          </div>
        ))}
        {loading ? <div className="spar-loading">Thinking with Claude Code…</div> : null}
      </div>
      <form
        className="spar-input-row"
        onSubmit={(event) => {
          event.preventDefault();
          void sendMessage();
        }}
      >
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Ask an architecture question…"
          disabled={loading}
        />
        <button type="submit" disabled={loading || !input.trim()}>
          Send
        </button>
      </form>
    </aside>
  );
}

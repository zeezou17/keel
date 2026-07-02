/**
 * Right-hand AI sparring chat (Cursor-style sessions in localStorage).
 *
 * Sends messages to POST /api/spar and can apply suggested diagram changes.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  createNode,
  spar,
  type ArchitectureFile,
  type KeelNode,
  type SparAction,
  type SparHistoryMessage,
  type SparMessage,
} from "../api/client";
import {
  deleteSession,
  ensureActiveSession,
  formatSessionTime,
  loadSparStore,
  normalizeSparStore,
  saveSparStore,
  selectSession,
  sortedSessions,
  startNewSession,
  titleFromMessage,
  updateSessionMessages,
  type SparSession,
  type SparStore,
} from "../spar/sessions";
import { SparMessageContent } from "./SparMessageContent";

interface SparringPanelProps {
  level: number;
  containerId?: string | null;
  collapsed: boolean;
  onToggleCollapsed: () => void;
  onArchitectureUpdated: (architecture: ArchitectureFile) => void;
}

function toApiHistory(messages: SparMessage[]): SparHistoryMessage[] {
  return messages
    .filter((message): message is SparMessage & { role: "user" | "assistant" } =>
      message.role === "user" || message.role === "assistant",
    )
    .map((message) => ({
      role: message.role,
      content: message.content,
    }));
}

export function SparringPanel({
  level,
  containerId,
  collapsed,
  onToggleCollapsed,
  onArchitectureUpdated,
}: SparringPanelProps) {
  const [store, setStore] = useState<SparStore>(() => normalizeSparStore(loadSparStore()));
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionsOpen, setSessionsOpen] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const sessionsMenuRef = useRef<HTMLDivElement>(null);

  const normalizedContainerId = containerId ?? null;

  useEffect(() => {
    saveSparStore(store);
  }, [store]);

  useEffect(() => {
    if (!collapsed) {
      inputRef.current?.focus();
    }
  }, [collapsed, store.activeSessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [store.activeSessionId, store.sessions, loading]);

  useEffect(() => {
    if (!sessionsOpen) {
      return;
    }
    const onPointerDown = (event: MouseEvent) => {
      if (!sessionsMenuRef.current?.contains(event.target as Node)) {
        setSessionsOpen(false);
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [sessionsOpen]);

  const activeSession = useMemo(
    () => store.sessions.find((session) => session.id === store.activeSessionId) ?? null,
    [store],
  );

  const sessionList = useMemo(() => sortedSessions(store.sessions), [store.sessions]);

  const messages = activeSession?.messages ?? [];

  const patchStore = useCallback((updater: (current: SparStore) => SparStore) => {
    setStore((current) => updater(current));
  }, []);

  const handleNewSession = useCallback(() => {
    patchStore((current) => startNewSession(current, level, normalizedContainerId));
    setInput("");
    setSessionsOpen(false);
  }, [level, normalizedContainerId, patchStore]);

  const handleSelectSession = useCallback(
    (sessionId: string) => {
      patchStore((current) => selectSession(current, sessionId));
      setInput("");
      setSessionsOpen(false);
    },
    [patchStore],
  );

  const handleDeleteSession = useCallback(
    (sessionId: string, event: React.MouseEvent) => {
      event.stopPropagation();
      patchStore((current) => deleteSession(current, sessionId));
    },
    [patchStore],
  );

  const sendMessage = async () => {
    const trimmed = input.trim();
    if (!trimmed || loading) {
      return;
    }

    let workingStore = store;
    let session: SparSession;
    if (activeSession) {
      session = activeSession;
    } else {
      const ensured = ensureActiveSession(store, level, normalizedContainerId);
      workingStore = ensured.store;
      session = ensured.session;
      setStore(workingStore);
    }

    const userMessage: SparMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmed,
    };
    const priorMessages = session.messages;
    const nextMessages = [...priorMessages, userMessage];
    const nextTitle =
      priorMessages.length === 0 ? titleFromMessage(trimmed) : session.title;

    const sessionId = session.id;

    const withUser = updateSessionMessages(
      workingStore,
      sessionId,
      nextMessages,
      nextTitle,
    );
    setStore(withUser);
    setInput("");
    setLoading(true);

    try {
      const response = await spar(
        trimmed,
        level,
        normalizedContainerId,
        toApiHistory(priorMessages),
      );
      setStore((current) =>
        updateSessionMessages(current, sessionId, [
          ...nextMessages,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content: response.reply,
            actions: response.actions,
          },
        ]),
      );
    } catch (err) {
      setStore((current) =>
        updateSessionMessages(current, sessionId, [
          ...nextMessages,
          {
            id: crypto.randomUUID(),
            role: "error",
            content: err instanceof Error ? err.message : "Claude Code request failed.",
          },
        ]),
      );
    } finally {
      setLoading(false);
    }
  };

  const applyAction = async (action: SparAction) => {
    if (action.type !== "add_node" || !activeSession) {
      return;
    }
    try {
      const updated = await createNode(action.level, action.node as KeelNode, action.container_id);
      if (action.level === level && (action.container_id ?? null) === normalizedContainerId) {
        onArchitectureUpdated(updated);
      }
      setStore((current) =>
        updateSessionMessages(current, activeSession.id, [
          ...activeSession.messages,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content: `Applied: ${action.label}`,
          },
        ]),
      );
    } catch (err) {
      setStore((current) =>
        updateSessionMessages(current, activeSession.id, [
          ...activeSession.messages,
          {
            id: crypto.randomUUID(),
            role: "error",
            content: err instanceof Error ? err.message : "Failed to apply suggestion.",
          },
        ]),
      );
    }
  };

  const handleComposerKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    event.stopPropagation();
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage();
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
        <div className="spar-header-main" ref={sessionsMenuRef}>
          <button
            type="button"
            className="spar-session-trigger"
            onClick={() => setSessionsOpen((open) => !open)}
            aria-expanded={sessionsOpen}
            aria-haspopup="listbox"
          >
            <span className="spar-session-title">{activeSession?.title ?? "New chat"}</span>
            <span className="spar-session-caret" aria-hidden>
              ▾
            </span>
          </button>
          {sessionsOpen ? (
            <div className="spar-sessions-menu" role="listbox">
              {sessionList.length === 0 ? (
                <p className="spar-sessions-empty">No saved chats yet.</p>
              ) : (
                sessionList.map((session) => (
                  <div
                    key={session.id}
                    role="option"
                    aria-selected={session.id === store.activeSessionId}
                    className={`spar-session-item${
                      session.id === store.activeSessionId ? " active" : ""
                    }`}
                    onClick={() => handleSelectSession(session.id)}
                  >
                    <div className="spar-session-item-text">
                      <span className="spar-session-item-title">{session.title}</span>
                      <span className="spar-session-item-meta">
                        {formatSessionTime(session.updatedAt)} · C{session.viewLevel}
                      </span>
                    </div>
                    <button
                      type="button"
                      className="spar-session-delete"
                      aria-label={`Delete ${session.title}`}
                      onClick={(event) => handleDeleteSession(session.id, event)}
                    >
                      ×
                    </button>
                  </div>
                ))
              )}
            </div>
          ) : null}
        </div>
        <div className="spar-header-actions">
          <button
            type="button"
            className="spar-icon-button"
            onClick={handleNewSession}
            title="New chat"
            aria-label="New chat"
          >
            +
          </button>
          <button className="spar-toggle" onClick={onToggleCollapsed}>
            Collapse
          </button>
        </div>
      </div>

      <div className="spar-messages">
        {messages.length === 0 ? (
          <div className="spar-empty-state">
            <p className="spar-empty-title">Architecture sparring</p>
            <p className="spar-empty">
              Ask about trade-offs, missing containers, or drift risks. Chats are saved locally in
              this browser — use the title dropdown above to switch between previous conversations.
            </p>
          </div>
        ) : null}
        {messages.map((message) => (
          <div key={message.id} className={`spar-message ${message.role}`}>
            <div className="spar-message-label">
              {message.role === "user" ? "You" : message.role === "error" ? "Error" : "Assistant"}
            </div>
            {message.role === "assistant" || message.role === "error" ? (
              <SparMessageContent content={message.content} />
            ) : (
              <div className="spar-message-body">{message.content}</div>
            )}
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
        {loading ? (
          <div className="spar-message assistant loading">
            <div className="spar-message-label">Assistant</div>
            <div className="spar-message-body spar-loading">Thinking with Claude Code…</div>
          </div>
        ) : null}
        <div ref={messagesEndRef} />
      </div>

      <form
        className="spar-composer"
        onSubmit={(event) => {
          event.preventDefault();
          void sendMessage();
        }}
        onKeyDown={(event) => event.stopPropagation()}
      >
        <textarea
          ref={inputRef}
          className="spar-composer-input"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleComposerKeyDown}
          placeholder="Ask a follow-up…"
          rows={3}
          aria-label="Sparring message"
        />
        <div className="spar-composer-footer">
          <span className="spar-composer-hint">Enter to send · Shift+Enter for newline</span>
          <button type="submit" className="spar-send-button" disabled={loading || !input.trim()}>
            {loading ? "Waiting…" : "Send"}
          </button>
        </div>
      </form>
    </aside>
  );
}

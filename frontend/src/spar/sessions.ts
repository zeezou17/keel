/**
 * Local-only storage for AI sparring chat sessions (browser localStorage).
 *
 * Not synced to the server — each browser keeps its own chat history.
 */
import type { SparMessage } from "../api/client";

const STORAGE_KEY = "keel:spar-sessions";

export interface SparSession {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: SparMessage[];
  viewLevel: number;
  containerId: string | null;
}

export interface SparStore {
  activeSessionId: string | null;
  sessions: SparSession[];
}

// -- Load/save entire store --------------------------------------------------


function emptyStore(): SparStore {
  return { activeSessionId: null, sessions: [] };
}

export function titleFromMessage(text: string): string {
  const trimmed = text.trim().replace(/\s+/g, " ");
  if (!trimmed) {
    return "New chat";
  }
  return trimmed.length <= 48 ? trimmed : `${trimmed.slice(0, 45)}…`;
}

export function loadSparStore(): SparStore {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return emptyStore();
    }
    const parsed = JSON.parse(raw) as SparStore;
    if (!Array.isArray(parsed.sessions)) {
      return emptyStore();
    }
    return {
      activeSessionId: parsed.activeSessionId ?? null,
      sessions: parsed.sessions,
    };
  } catch {
    return emptyStore();
  }
}

export function saveSparStore(store: SparStore): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
}

// -- Session CRUD (create, select, delete, update messages) --------------------


export function createSession(viewLevel: number, containerId: string | null): SparSession {
  const now = new Date().toISOString();
  return {
    id: crypto.randomUUID(),
    title: "New chat",
    createdAt: now,
    updatedAt: now,
    messages: [],
    viewLevel,
    containerId,
  };
}

export function ensureActiveSession(
  store: SparStore,
  viewLevel: number,
  containerId: string | null,
): { store: SparStore; session: SparSession } {
  const active = store.sessions.find((item) => item.id === store.activeSessionId);
  if (active) {
    return { store, session: active };
  }

  const session = createSession(viewLevel, containerId);
  const next: SparStore = {
    activeSessionId: session.id,
    sessions: [session, ...store.sessions],
  };
  return { store: next, session };
}

export function startNewSession(
  store: SparStore,
  viewLevel: number,
  containerId: string | null,
): SparStore {
  const session = createSession(viewLevel, containerId);
  return {
    activeSessionId: session.id,
    sessions: [session, ...store.sessions],
  };
}

export function selectSession(store: SparStore, sessionId: string): SparStore {
  if (!store.sessions.some((item) => item.id === sessionId)) {
    return store;
  }
  return { ...store, activeSessionId: sessionId };
}

export function deleteSession(store: SparStore, sessionId: string): SparStore {
  const sessions = store.sessions.filter((item) => item.id !== sessionId);
  if (sessions.length === 0) {
    return emptyStore();
  }
  const activeSessionId =
    store.activeSessionId === sessionId ? sessions[0].id : store.activeSessionId;
  return { activeSessionId, sessions };
}

export function updateSessionMessages(
  store: SparStore,
  sessionId: string,
  messages: SparMessage[],
  title?: string,
): SparStore {
  const now = new Date().toISOString();
  return {
    ...store,
    sessions: store.sessions.map((session) =>
      session.id === sessionId
        ? {
            ...session,
            messages,
            title: title ?? session.title,
            updatedAt: now,
          }
        : session,
    ),
  };
}

// -- Display helpers for the session dropdown ----------------------------------


export function sortedSessions(sessions: SparSession[]): SparSession[] {
  return [...sessions].sort(
    (left, right) => new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime(),
  );
}

export function formatSessionTime(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const sameDay =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate();
  if (sameDay) {
    return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }
  return date.toLocaleDateString([], { month: "short", day: "numeric" });
}

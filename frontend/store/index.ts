import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface GraphNode {
  id: string;
  summary: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  label: string;
  explanation: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  origin: string;
}

export interface CacheEntry<T> {
  data: T;
  cachedAt: number;
}

export const TTL_MS = 86400 * 1000;

export function isExpired(entry: CacheEntry<unknown>): boolean {
  return Date.now() - entry.cachedAt > TTL_MS;
}

function sweepCache<T>(
  cache: Record<string, CacheEntry<T>>
): Record<string, CacheEntry<T>> {
  const now = Date.now();
  const out: Record<string, CacheEntry<T>> = {};
  for (const [k, v] of Object.entries(cache)) {
    if (now - v.cachedAt <= TTL_MS) out[k] = v;
  }
  return out;
}

type PrefetchStatus = "idle" | "loading" | "done" | "error";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyCache = Record<string, CacheEntry<any>>;

interface AppState {
  sessionId: string;
  darkMode: boolean;
  activeTopic: string;
  graphCache: Record<string, CacheEntry<GraphData>>;
  debateCache: AnyCache;
  perspectiveCache: AnyCache;
  prefetchStatus: Record<string, PrefetchStatus>;

  setSessionId: (id: string) => void;
  setDarkMode: (dark: boolean) => void;
  setActiveTopic: (topic: string) => void;
  setGraphCache: (topic: string, data: GraphData) => void;
  setDebateCache: (topic: string, data: unknown) => void;
  setPerspectiveCache: (topic: string, data: unknown) => void;
  setPrefetchStatus: (topic: string, status: PrefetchStatus) => void;
}

function generateSessionId(): string {
  return crypto.randomUUID();
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      sessionId: generateSessionId(),
      darkMode: false,
      activeTopic: "",
      graphCache: {},
      debateCache: {},
      perspectiveCache: {},
      prefetchStatus: {},

      setSessionId: (id) => set({ sessionId: id }),
      setDarkMode: (dark) => set({ darkMode: dark }),
      setActiveTopic: (topic) => set({ activeTopic: topic }),
      setGraphCache: (topic, data) =>
        set((s) => ({
          graphCache: {
            ...s.graphCache,
            [topic]: { data, cachedAt: Date.now() },
          },
        })),
      setDebateCache: (topic, data) =>
        set((s) => ({
          debateCache: {
            ...s.debateCache,
            [topic]: { data, cachedAt: Date.now() },
          },
        })),
      setPerspectiveCache: (topic, data) =>
        set((s) => ({
          perspectiveCache: {
            ...s.perspectiveCache,
            [topic]: { data, cachedAt: Date.now() },
          },
        })),
      setPrefetchStatus: (topic, status) =>
        set((s) => ({
          prefetchStatus: { ...s.prefetchStatus, [topic]: status },
        })),
    }),
    {
      name: "rabbitpedia-store",
      version: 3,
      migrate: () => ({
        sessionId: generateSessionId(),
        darkMode: false,
        activeTopic: "",
        graphCache: {},
        debateCache: {},
        perspectiveCache: {},
        prefetchStatus: {},
      }),
      onRehydrateStorage: () => (state) => {
        if (!state) return;
        state.graphCache = sweepCache(state.graphCache);
        state.debateCache = sweepCache(state.debateCache);
        state.perspectiveCache = sweepCache(state.perspectiveCache);
      },
      partialize: (s) => ({
        sessionId: s.sessionId,
        darkMode: s.darkMode,
        activeTopic: s.activeTopic,
        graphCache: s.graphCache,
        debateCache: s.debateCache,
        perspectiveCache: s.perspectiveCache,
        prefetchStatus: s.prefetchStatus,
      }),
    }
  )
);

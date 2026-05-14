"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useAppStore, isExpired } from "@/store";

interface Narrator {
  id: string;
  name: string;
  stance: string;
  color: string;
}

interface PerspectiveSection {
  narrator: Narrator;
  title: string;
  body: string;
  what_they_emphasize: string;
  what_they_omit: string;
  most_revealing_line: string;
}

interface PerspectiveData {
  topic: string;
  origin_summary: string;
  perspectives: PerspectiveSection[];
}

function PerspectiveBlock({ p }: { p: PerspectiveSection }) {
  return (
    <div className="perspective-section">
      <div className="perspective-color-bar" style={{ background: p.narrator.color }} />
      <div className="perspective-content">
        <div className="perspective-narrator-header">
          <div className="perspective-narrator-name">{p.narrator.name}</div>
          <div className="perspective-narrator-stance">{p.narrator.stance}</div>
        </div>

        <div className="perspective-title">{p.title}</div>

        <div className="perspective-body">{p.body}</div>

        <blockquote className="perspective-revealing-line">
          &ldquo;{p.most_revealing_line}&rdquo;
        </blockquote>

        <div className="perspective-meta-row">
          <div className="perspective-meta-item">
            <div className="perspective-meta-label">What they focus on</div>
            <div className="perspective-meta-value">{p.what_they_emphasize}</div>
          </div>
          <div className="perspective-meta-item">
            <div className="perspective-meta-label">What they ignore</div>
            <div className="perspective-meta-value">{p.what_they_omit}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function PerspectivesPage() {
  const activeTopic = useAppStore((s) => s.activeTopic);
  const darkMode = useAppStore((s) => s.darkMode);
  const setDarkMode = useAppStore((s) => s.setDarkMode);
  const perspectiveCache = useAppStore((s) => s.perspectiveCache);
  const setPerspectiveCache = useAppStore((s) => s.setPerspectiveCache);

  const [query, setQuery] = useState("");
  const [data, setData] = useState<PerspectiveData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastLoadedTopicRef = useRef("");

  useEffect(() => {
    if (!activeTopic || lastLoadedTopicRef.current === activeTopic) return;
    lastLoadedTopicRef.current = activeTopic;
    setQuery(activeTopic);
    const cached = perspectiveCache[activeTopic];
    if (cached && !isExpired(cached)) {
      setData(cached.data as PerspectiveData);
    } else {
      fetchPerspectives(activeTopic);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTopic]);

  async function fetchPerspectives(q: string) {
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const resp = await fetch(`http://localhost:8000/perspective?query=${encodeURIComponent(q)}`);
      if (!resp.ok) throw new Error("Could not find perspectives for this topic.");
      const result = await resp.json();
      setData(result);
      setPerspectiveCache(q, result);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not find perspectives. Try another topic.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="perspectives-page">
      <header className="wiki-header">
        <div className="wiki-header-inner">
          <h1><span className="logo-rabbit">Rabbit</span>Pedia</h1>
          <nav className="header-nav">
            <Link href="/" className="nav-link">Home</Link>
            <Link href="/graph" className="nav-link">Knowledge Graph</Link>
            <Link href="/debate" className="nav-link">Debate</Link>
            <Link href="/perspectives" className="nav-link active">Flip the Lens</Link>
            <Link href="/curiosity-path" className="nav-link">My Path</Link>
          </nav>
          <div className="toolbar-actions">
            <button className="toolbar-icon" onClick={() => setDarkMode(!darkMode)}>
              {darkMode ? "Light" : "Dark"}
            </button>
          </div>
        </div>
      </header>

      <div className="perspectives-body">
        <div className="debate-header-bar">
          <div className="debate-search-bar">
            <input
              type="text"
              placeholder="Enter a topic to flip the lens..."
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === "Enter" && fetchPerspectives(query)}
              disabled={loading}
            />
            <button onClick={() => fetchPerspectives(query)} disabled={loading || !query.trim()}>
              {loading ? "Gathering voices…" : "Flip Lens"}
            </button>
          </div>
        </div>

        {loading && (
          <div className="perspectives-loading">Gathering perspectives…</div>
        )}

        {error && (
          <div className="perspectives-error" style={{ color: "var(--debate-red)" }}>{error}</div>
        )}

        {!loading && !error && !data && (
          <div className="perspectives-loading" style={{ color: "var(--text-faint)", fontFamily: "Arial, sans-serif", fontSize: 14 }}>
            Choose a topic to see history through different eyes.
          </div>
        )}

        {data && (
          <>
            <p className="perspectives-origin">{data.origin_summary}</p>
            {data.perspectives.map(p => (
              <PerspectiveBlock key={p.narrator.id} p={p} />
            ))}
          </>
        )}
      </div>
    </div>
  );
}

"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import CuriosityPathGraph from "../../components/CuriosityPathGraph";
import CuriosityInsightPanel from "../../components/CuriosityInsightPanel";
import { useAppStore } from "@/store";

function useResize(initialWidth: number, min: number, max: number) {
  const [width, setWidth] = useState(initialWidth);
  function onMouseDown(e: React.MouseEvent) {
    e.preventDefault();
    const startX = e.clientX;
    const startW = width;
    function onMove(ev: MouseEvent) {
      setWidth(Math.min(max, Math.max(min, startW - (ev.clientX - startX))));
    }
    function onUp() {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    }
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }
  return { width, onMouseDown };
}

interface PathNode {
  id: string;
  title: string;
  order: number;
  summary: string;
  why_interesting: string;
}

interface PathEdge {
  source: string;
  target: string;
  transition: string;
}

interface CuriosityInsight {
  pattern: string;
  theme: string;
  most_unexpected_jump: string;
  rabbit_hole_depth: string;
  next_recommendation: string;
}

interface PathData {
  session_id: string;
  nodes: PathNode[];
  edges: PathEdge[];
  insight: CuriosityInsight;
  total_topics: number;
  session_duration_minutes: number;
}

export default function CuriosityPathPage() {
  const sessionId = useAppStore((s) => s.sessionId);
  const darkMode = useAppStore((s) => s.darkMode);
  const setDarkMode = useAppStore((s) => s.setDarkMode);

  const [data, setData] = useState<PathData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<PathNode | null>(null);
  const [hoveredEdge, setHoveredEdge] = useState<PathEdge | null>(null);
  const [d3Loaded] = useState(true);
  const vizRef = useRef<HTMLDivElement>(null);
  const { width: panelWidth, onMouseDown: onPanelResizeStart } = useResize(340, 240, 560);

  useEffect(() => {
    if (sessionId) fetchPath(sessionId);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  async function fetchPath(sid: string) {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`http://localhost:8000/path?session_id=${sid}`);
      if (resp.status === 404) {
        setData(null);
      } else if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || "Could not generate curiosity path.");
      } else {
        setData(await resp.json());
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not generate curiosity path.");
    } finally {
      setLoading(false);
    }
  }

  async function handleShare() {
    if (!vizRef.current) return;
    const { default: html2canvas } = await import("html2canvas");
    const canvas = await html2canvas(vizRef.current);
    const link = document.createElement("a");
    link.download = "my-curiosity-path.png";
    link.href = canvas.toDataURL("image/png");
    link.click();
  }

  function handleDownloadJSON() {
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.download = `curiosity-path-${data.session_id}.json`;
    link.href = url;
    link.click();
    URL.revokeObjectURL(url);
  }

  const prevTransition = selectedNode
    ? data?.edges.find(
        e => e.target === selectedNode.id &&
          data.nodes.findIndex(n => n.id === e.source) === data.nodes.findIndex(n => n.id === selectedNode.id) - 1
      )?.transition
    : null;

  return (
    <div className="page" style={{ height: "100vh", display: "flex", flexDirection: "column", overflow: "hidden", background: "var(--bg-page)" }}>


      <header className="wiki-header">
        <div className="wiki-header-inner">
          <h1><span className="logo-rabbit">Rabbit</span>Pedia</h1>
          <nav className="header-nav">
            <Link href="/" className="nav-link">Home</Link>
            <Link href="/graph" className="nav-link">Knowledge Graph</Link>
            <Link href="/debate" className="nav-link">Debate</Link>
            <Link href="/perspectives" className="nav-link">Flip the Lens</Link>
            <Link href="/curiosity-path" className="nav-link active">My Path</Link>
          </nav>
          <div className="toolbar-actions">
            <button className="toolbar-icon" onClick={() => setDarkMode(!darkMode)}>
              {darkMode ? "Light" : "Dark"}
            </button>
          </div>
        </div>
      </header>

      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: 32 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
            <div>
              <h2 style={{ fontFamily: '"Linux Libertine", Georgia, serif', fontSize: 28, fontWeight: 400, marginBottom: 4 }}>
                Your Curiosity Path
              </h2>
              {data && (
                <p style={{ fontSize: 13, color: "var(--text-muted)", fontFamily: "Arial, sans-serif" }}>
                  {data.session_duration_minutes} min journey · {data.total_topics} topics explored
                </p>
              )}
            </div>
            {data && (
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  onClick={handleShare}
                  style={{ padding: "6px 14px", background: "var(--text-link)", color: "#fff", border: "none", borderRadius: 2, fontSize: 13, cursor: "pointer" }}
                >
                  Share Map
                </button>
                <button
                  onClick={handleDownloadJSON}
                  style={{ padding: "6px 14px", background: "var(--bg-content)", color: "var(--text-body)", border: "1px solid var(--border-strong)", borderRadius: 2, fontSize: 13, cursor: "pointer" }}
                >
                  Download JSON
                </button>
              </div>
            )}
          </div>

          <div
            ref={vizRef}
            style={{
              flex: 1, background: "var(--bg-content)", border: "1px solid var(--border-strong)",
              borderRadius: 2, position: "relative", overflow: "hidden",
            }}
          >
            {(loading || !d3Loaded) ? (
              <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: '"Linux Libertine", Georgia, serif', fontSize: 18, color: "var(--text-muted)" }}>
                {loading ? "Tracing your curiosity trail…" : "Loading visualization…"}
              </div>
            ) : error ? (
              <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", color: "var(--debate-red)", textAlign: "center", padding: 40 }}>
                <p style={{ marginBottom: 16 }}>{error}</p>
                <Link href="/" style={{ color: "var(--text-link)" }}>Back to RabbitPedia</Link>
              </div>
            ) : !data ? (
              <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", padding: 40 }}>
                <h3 style={{ fontFamily: '"Linux Libertine", Georgia, serif', fontWeight: 400, marginBottom: 10 }}>
                  You haven&apos;t explored anything yet.
                </h3>
                <p style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 20 }}>
                  Start a rabbit hole on the home page to see your path grow.
                </p>
                <Link href="/" style={{ padding: "8px 20px", background: "var(--text-link)", color: "#fff", borderRadius: 2, textDecoration: "none", fontSize: 13 }}>
                  Start Exploring
                </Link>
              </div>
            ) : (
              <>
                <CuriosityPathGraph
                  nodes={data.nodes}
                  edges={data.edges}
                  onNodeClick={setSelectedNode}
                  onEdgeHover={setHoveredEdge}
                  darkMode={darkMode}
                />
                {hoveredEdge && (
                  <div style={{
                    position: "absolute", bottom: 24, left: "50%", transform: "translateX(-50%)",
                    background: "var(--text-body)", color: "#fff", padding: "6px 14px",
                    borderRadius: 2, fontSize: 12, pointerEvents: "none", zIndex: 10,
                  }}>
                    {hoveredEdge.transition}
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        <div style={{ position: "relative", width: panelWidth, flexShrink: 0, background: "var(--bg-content)", borderLeft: "1px solid var(--border-strong)", overflow: "auto" }}>
          <div
            onMouseDown={onPanelResizeStart}
            style={{
              position: "absolute", top: 0, left: 0, width: 4, height: "100%",
              cursor: "ew-resize", zIndex: 10, background: "transparent",
            }}
            onMouseEnter={e => (e.currentTarget.style.background = "var(--text-link)")}
            onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
          />
          {data && (
            <CuriosityInsightPanel
              insight={data.insight}
              selectedNode={selectedNode}
              previousTransition={prevTransition || null}
              onBackToProfile={() => setSelectedNode(null)}
            />
          )}
        </div>
      </div>
    </div>
  );
}

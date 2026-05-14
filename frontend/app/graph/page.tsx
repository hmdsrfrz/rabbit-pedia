"use client";

import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import ChatPanel, { ChatPanelHandle } from "../../components/ChatPanel";
import Link from "next/link";
import { useAppStore, isExpired, CacheEntry, GraphData } from "@/store";

interface GraphNode {
  id: string;
  summary: string;
}

interface GraphEdge {
  source: string;
  target: string;
  label: string;
  explanation: string;
}

interface GraphData_ {
  nodes: GraphNode[];
  edges: GraphEdge[];
  origin: string;
}

// ─── History sidebar ──────────────────────────────────────────

function useResize(initialWidth: number, min: number, max: number) {
  const [width, setWidth] = useState(initialWidth);

  function onMouseDown(e: React.MouseEvent) {
    e.preventDefault();
    const startX = e.clientX;
    const startW = width;

    function onMove(ev: MouseEvent) {
      setWidth(Math.min(max, Math.max(min, startW + ev.clientX - startX)));
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

function GraphHistorySidebar({
  entries,
  currentTopic,
  onSelect,
  open,
  onClose,
  width,
  onResizeStart,
}: {
  entries: { topic: string; cachedAt: number }[];
  currentTopic: string;
  onSelect: (topic: string) => void;
  open: boolean;
  onClose: () => void;
  width: number;
  onResizeStart: (e: React.MouseEvent) => void;
}) {
  return (
    <div
      className={`ghs${open ? " ghs-open" : ""}`}
      style={{ width: open ? width : 0 }}
    >
      <div className="ghs-inner" style={{ width }}>
        <div className="sidebar-header">
          <span className="sidebar-title">Graph History</span>
          <button className="sidebar-close" onClick={onClose}>×</button>
        </div>
        {entries.length === 0 ? (
          <p className="sidebar-empty">Topics you graph will appear here.</p>
        ) : (
          <div className="ghs-list">
            {entries.map(({ topic }) => (
              <button
                key={topic}
                className={`ghs-item${topic === currentTopic ? " ghs-item-active" : ""}`}
                onClick={() => onSelect(topic)}
              >
                {topic}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="ghs-resize-handle" onMouseDown={onResizeStart} />
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────

export default function GraphPage() {
  const activeTopic = useAppStore((s) => s.activeTopic);
  const graphCache = useAppStore((s) => s.graphCache);
  const prefetchStatus = useAppStore((s) => s.prefetchStatus);
  const setGraphCache = useAppStore((s) => s.setGraphCache);
  const setPrefetchStatus = useAppStore((s) => s.setPrefetchStatus);
  const darkMode = useAppStore((s) => s.darkMode);
  const setDarkMode = useAppStore((s) => s.setDarkMode);

  const [query, setQuery] = useState(activeTopic ?? "");
  const [graphData, setGraphData] = useState<GraphData_ | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const svgRef = useRef<SVGSVGElement>(null);
  const chatPanelRef = useRef<ChatPanelHandle>(null);
  const autoFetchedRef = useRef(false);
  const { width: sidebarWidth, onMouseDown: onResizeStart } = useResize(240, 180, 400);

  // Build history entries sorted most-recent first
  const historyEntries = Object.entries(graphCache)
    .map(([topic, entry]) => ({ topic, cachedAt: (entry as CacheEntry<GraphData>).cachedAt }))
    .sort((a, b) => b.cachedAt - a.cachedAt);

  useEffect(() => {
    if (!activeTopic || autoFetchedRef.current) return;
    autoFetchedRef.current = true;
    setQuery(activeTopic);
    const cached = graphCache[activeTopic];
    if (cached?.data?.nodes && cached?.data?.edges && !isExpired(cached)) {
      setGraphData(cached.data as GraphData_);
      chatPanelRef.current?.runQuery(activeTopic, { deep: false });
    } else {
      fetchGraph(activeTopic);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTopic]);

  useEffect(() => {
    if (graphData && svgRef.current) renderGraph();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graphData, darkMode]);

  function loadFromHistory(topic: string) {
    const cached = graphCache[topic];
    if (!cached?.data?.nodes || !cached?.data?.edges) return;
    setQuery(topic);
    setGraphData(cached.data as GraphData_);
    setSelectedNode(null);
    chatPanelRef.current?.runQuery(topic, { deep: false, skipTopicUpdate: true });
  }

  async function fetchGraph(searchQuery: string) {
    if (!searchQuery.trim()) return;

    const cached = graphCache[searchQuery];
    if (cached?.data?.nodes && cached?.data?.edges && !isExpired(cached)) {
      setGraphData(cached.data as GraphData_);
      chatPanelRef.current?.runQuery(searchQuery, { deep: false });
      chatPanelRef.current?.scrollToLatest();
      return;
    }

    setLoading(true);
    setError(null);
    setGraphData(null);
    setSelectedNode(null);
    setPrefetchStatus(searchQuery, "loading");

    try {
      const resp = await fetch(`http://localhost:8000/graph?query=${encodeURIComponent(searchQuery)}`);
      if (!resp.ok) throw new Error("Failed to build knowledge map.");
      const data = await resp.json();
      if (!data?.nodes || !data?.edges) throw new Error("Invalid graph data from server.");
      setGraphData(data);
      setGraphCache(searchQuery, data);
      setPrefetchStatus(searchQuery, "done");
      chatPanelRef.current?.runQuery(searchQuery, { deep: false });
      chatPanelRef.current?.scrollToLatest();
    } catch (err: unknown) {
      setPrefetchStatus(searchQuery, "error");
      setError(err instanceof Error ? err.message : "Could not build knowledge map for this topic.");
    } finally {
      setLoading(false);
    }
  }

  async function fetchConnection(node: string, origin: string) {
    const blockId = chatPanelRef.current?.addPendingBlock(`How is ${node} connected to ${origin}?`);
    if (!blockId) return;
    chatPanelRef.current?.scrollToLatest();
    try {
      const resp = await fetch(
        `http://localhost:8000/connection?node=${encodeURIComponent(node)}&origin=${encodeURIComponent(origin)}`
      );
      if (!resp.ok) throw new Error("connection failed");
      const data = await resp.json();
      chatPanelRef.current?.resolveBlock(blockId, {
        heading: data.heading,
        body: data.body,
        key_concepts: null,
        did_you_know: [],
        two_cents: "",
        sources: [
          ...(data.node_url ? [{ title: node, url: data.node_url }] : []),
          ...(data.origin_url ? [{ title: origin, url: data.origin_url }] : []),
        ],
        explore_further: { from_article: [], you_might_like: [] },
        conversational: false,
      });
    } catch {
      chatPanelRef.current?.resolveBlock(blockId, {
        heading: `${node} — ${origin}`,
        body: "Could not load the connection. Try clicking the node again.",
        key_concepts: null,
        did_you_know: [],
        two_cents: "",
        sources: [],
        explore_further: { from_article: [], you_might_like: [] },
        conversational: false,
      });
    }
  }

  function renderGraph() {
    if (!graphData || !graphData.nodes || !graphData.edges || !svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const width = svgRef.current.clientWidth || 800;
    const height = svgRef.current.clientHeight || 600;
    svg.attr("viewBox", `0 0 ${width} ${height}`);

    const validNodeIds = new Set(graphData.nodes.map((n: GraphNode) => n.id));
    const validEdges = graphData.edges.filter((e: GraphEdge) =>
      validNodeIds.has(typeof e.source === "string" ? e.source : (e.source as unknown as { id: string }).id) &&
      validNodeIds.has(typeof e.target === "string" ? e.target : (e.target as unknown as { id: string }).id)
    );

    const nodes = graphData.nodes.map((n: GraphNode) => ({ ...n }));
    const links = validEdges.map((e: GraphEdge) => ({ ...e }));

    const simulation = d3.forceSimulation(nodes as any)
      .force("link", d3.forceLink(links as any).id((d: any) => d.id).distance(100))
      .force("charge", d3.forceManyBody().strength(-150))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide().radius(40));

    const g = svg.append("g");
    const zoom = d3.zoom().on("zoom", (event: any) => g.attr("transform", event.transform));
    (svg as any).call(zoom);

    const link = g.append("g")
      .selectAll("line").data(links).join("line")
      .attr("stroke", "#a2a9b1")
      .attr("stroke-opacity", 0.4)
      .attr("stroke-width", 1);

    const node = g.append("g")
      .selectAll("g").data(nodes).join("g")
      .style("cursor", "pointer")
      .call((d3.drag() as any)
        .on("start", (event: any) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          event.subject.fx = event.subject.x;
          event.subject.fy = event.subject.y;
        })
        .on("drag", (event: any) => {
          event.subject.fx = event.x;
          event.subject.fy = event.y;
        })
        .on("end", (event: any) => {
          if (!event.active) simulation.alphaTarget(0);
          event.subject.fx = null;
          event.subject.fy = null;
        }))
      .on("click", (_event: any, d: any) => {
        setSelectedNode(d);
        fetchConnection(d.id, graphData.origin);
      });

    node.append("circle")
      .attr("r", (d: any) => d.id === graphData.origin ? 10 : 5)
      .attr("fill", (d: any) => d.id === graphData.origin ? "#f6c90e" : "#3366cc")
      .attr("stroke", "#fff")
      .attr("stroke-width", 1.5);

    node.append("text")
      .attr("dy", 15)
      .attr("text-anchor", "middle")
      .attr("font-family", "Arial, sans-serif")
      .attr("font-size", "10px")
      .attr("fill", darkMode ? "#f8f9fa" : "#202122")
      .text((d: any) => d.id.length > 15 ? d.id.substring(0, 12) + "..." : d.id);

    simulation.on("tick", () => {
      link
        .attr("x1", (d: any) => d.source.x)
        .attr("y1", (d: any) => d.source.y)
        .attr("x2", (d: any) => d.target.x)
        .attr("y2", (d: any) => d.target.y);
      node.attr("transform", (d: any) => `translate(${d.x},${d.y})`);
    });
  }

  function handleNodeHighlight(topic: string) {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll("circle")
      .filter((d: any) => d && d.id === topic)
      .transition().duration(500).attr("r", 20)
      .transition().duration(500).attr("r", (d: any) => d.id === graphData?.origin ? 12 : 8);
  }

  const connectedEdges = graphData?.edges?.filter(e =>
    (typeof e.source === "string" ? e.source : (e.source as any).id) === selectedNode?.id ||
    (typeof e.target === "string" ? e.target : (e.target as any).id) === selectedNode?.id
  ) || [];

  const isLoading = loading || prefetchStatus[query] === "loading";

  return (
    <div className="page">
      <header className="wiki-header">
        <div className="wiki-header-inner">
          <button
            className="sidebar-toggle"
            onClick={() => setSidebarOpen(o => !o)}
            aria-label="Toggle graph history"
            title="Graph history"
          >
            &#9776;
          </button>
          <h1><span className="logo-rabbit">Rabbit</span>Pedia</h1>
          <nav className="header-nav">
            <Link href="/" className="nav-link">Home</Link>
            <Link href="/graph" className="nav-link active">Knowledge Graph</Link>
            <Link href="/debate" className="nav-link">Debate</Link>
            <Link href="/perspectives" className="nav-link">Flip the Lens</Link>
            <Link href="/curiosity-path" className="nav-link">My Path</Link>
          </nav>
          <div className="toolbar-actions">
            <button className="toolbar-icon" onClick={() => setDarkMode(!darkMode)}>
              {darkMode ? "Light" : "Dark"}
            </button>
          </div>
        </div>
      </header>

      <div className="graph-layout">
        <GraphHistorySidebar
          entries={historyEntries}
          currentTopic={query}
          onSelect={loadFromHistory}
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          width={sidebarWidth}
          onResizeStart={onResizeStart}
        />

        <div className="graph-main">
          <div className="debate-header-bar">
            <div className="debate-search-bar">
              <input
                type="text"
                placeholder="Map a topic..."
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={e => e.key === "Enter" && fetchGraph(query)}
                disabled={isLoading}
              />
              <button
                onClick={() => fetchGraph(query)}
                disabled={isLoading || !query.trim()}
              >
                {isLoading ? "Building…" : "Build Map"}
              </button>
            </div>
          </div>

        <div className="graph-container">
          {isLoading && <div className="graph-loading">Building knowledge map…</div>}
          {error && <div className="graph-error">{error}</div>}
          {!isLoading && !error && !graphData && (
            <div className="empty-state" style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%,-50%)" }}>
              Search for a topic to see its knowledge graph.
            </div>
          )}
          <svg ref={svgRef} className="graph-svg" />

          <div className={`node-detail-panel ${selectedNode ? "panel-open" : ""}`}>
            {selectedNode && (
              <>
                <div className="detail-header">
                  <h3 className="detail-title">{selectedNode.id}</h3>
                  <button className="detail-close" onClick={() => setSelectedNode(null)}>×</button>
                </div>
                <p className="detail-summary">{selectedNode.summary}</p>
                <div>
                  {connectedEdges.map((edge, i) => (
                    <div key={i} className="connection-item">
                      <div className="connection-label">
                        {typeof edge.source === "string" ? edge.source : (edge.source as any).id}
                        {" → "}
                        {typeof edge.target === "string" ? edge.target : (edge.target as any).id}: {edge.label}
                      </div>
                      <div className="connection-explanation">{edge.explanation}</div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>

        </div>

        <ChatPanel
          ref={chatPanelRef}
          position="right"
          storageKey="graph-blocks"
          onNodeHighlight={handleNodeHighlight}
        />
      </div>
    </div>
  );
}

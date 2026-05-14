"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import ChatPanel, { ChatPanelHandle, ResponseBlock } from "../components/ChatPanel";
import Link from "next/link";
import { useAppStore, isExpired } from "@/store";

function HomeSearchBar({ onSearch }: { onSearch: (q: string) => void }) {
  const [value, setValue] = useState("");
  function submit() {
    if (!value.trim()) return;
    onSearch(value.trim());
    setValue("");
  }
  return (
    <div className="home-search-bar">
      <input
        type="text"
        value={value}
        onChange={e => setValue(e.target.value)}
        onKeyDown={e => e.key === "Enter" && submit()}
        placeholder="Search any topic to start your rabbit hole…"
        autoFocus
      />
      <button onClick={submit} disabled={!value.trim()}>Search</button>
    </div>
  );
}

function buildTrailNumbers(blocks: ResponseBlock[]): Record<string, string> {
  const numbers: Record<string, string> = {};
  const childrenByParent: Record<string, ResponseBlock[]> = {};
  const roots: ResponseBlock[] = [];
  for (const b of blocks) {
    if (b.parentId) (childrenByParent[b.parentId] ||= []).push(b);
    else roots.push(b);
  }
  function walk(block: ResponseBlock, prefix: string) {
    numbers[block.id] = prefix;
    (childrenByParent[block.id] || []).forEach((c, i) => walk(c, `${prefix}.${i + 1}`));
  }
  roots.forEach((r, i) => walk(r, `${i + 1}`));
  return numbers;
}

function TrailNode({
  block,
  numbers,
  childrenByParent,
}: {
  block: ResponseBlock;
  numbers: Record<string, string>;
  childrenByParent: Record<string, ResponseBlock[]>;
}) {
  function scrollTo(id: string) {
    document.getElementById(`section-${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  const children = childrenByParent[block.id] || [];
  return (
    <li className="trail-item">
      <button className="trail-link" onClick={() => scrollTo(block.id)}>
        {block.section?.image_url && (
          // eslint-disable-next-line @next/next/no-img-element
          <img className="trail-thumb" src={block.section.image_url} alt="" width={32} height={32} />
        )}
        <span className="trail-label">
          <span className="trail-num">{numbers[block.id]}.</span>
          {block.section?.heading ?? block.query}
        </span>
      </button>
      {children.length > 0 && (
        <ul className="trail-item-children">
          {children.map(c => (
            <TrailNode key={c.id} block={c} numbers={numbers} childrenByParent={childrenByParent} />
          ))}
        </ul>
      )}
    </li>
  );
}

function Sidebar({ blocks, open, onClose }: { blocks: ResponseBlock[]; open: boolean; onClose: () => void }) {
  const numbers = buildTrailNumbers(blocks);
  const childrenByParent: Record<string, ResponseBlock[]> = {};
  const roots: ResponseBlock[] = [];
  for (const b of blocks) {
    if (b.parentId) (childrenByParent[b.parentId] ||= []).push(b);
    else roots.push(b);
  }
  return (
    <aside className={`sidebar${open ? " sidebar-open" : ""}`}>
      <div className="sidebar-inner">
        <div className="sidebar-header">
          <span className="sidebar-title">Rabbit Hole</span>
          <button className="sidebar-close" onClick={onClose} aria-label="Close sidebar">×</button>
        </div>
        {blocks.length === 0 ? (
          <p className="sidebar-empty">Your trail appears here as you explore.</p>
        ) : (
          <ol className="trail-list">
            {roots.map(r => (
              <TrailNode key={r.id} block={r} numbers={numbers} childrenByParent={childrenByParent} />
            ))}
          </ol>
        )}
      </div>
    </aside>
  );
}

function ExpiryWarning({ onDismiss }: { onDismiss: () => void }) {
  return (
    <div className="expiry-overlay" role="alert">
      <div className="expiry-popup">
        <p>Your session expires in under 2 hours. Your conversation history will be cleared.</p>
        <button className="expiry-dismiss" onClick={onDismiss}>Got it</button>
      </div>
    </div>
  );
}

function FirstLoadModal({ onDismiss }: { onDismiss: () => void }) {
  return (
    <div className="modal-overlay" role="dialog" aria-modal="true">
      <div className="modal">
        <h2>Welcome to RabbitPedia</h2>
        <p>
          Your conversation persists for <strong>24 hours</strong> —
          after that, your rabbit hole and history are cleared.
          Persistent accounts are coming soon.
        </p>
        <div className="modal-actions">
          <button className="modal-btn" onClick={onDismiss}>Got it</button>
        </div>
      </div>
    </div>
  );
}

function PdfPreparingModal() {
  return (
    <div className="modal-overlay" role="dialog" aria-modal="true">
      <div className="modal">
        <h2>Preparing your PDF</h2>
        <p><span className="spinner" />Capturing your conversation and assembling pages…</p>
      </div>
    </div>
  );
}

interface FeaturedArticle {
  title: string;
  extract: string;
}

function DiscoveryPanel({
  suggestedTopics,
  onTopicClick,
  onFeaturedClick,
}: {
  suggestedTopics: string[];
  onTopicClick: (t: string) => void;
  onFeaturedClick: (t: string) => void;
}) {
  const [featured, setFeatured] = useState<FeaturedArticle | null>(null);

  useEffect(() => {
    const today = new Date();
    const yyyy = today.getUTCFullYear();
    const mm = String(today.getUTCMonth() + 1).padStart(2, "0");
    const dd = String(today.getUTCDate()).padStart(2, "0");
    fetch(`https://en.wikipedia.org/api/rest_v1/feed/featured/${yyyy}/${mm}/${dd}`)
      .then(r => r.json())
      .then(data => {
        const tfa = data?.tfa;
        if (tfa) setFeatured({ title: tfa.title, extract: tfa.extract ?? "" });
      })
      .catch(() => {});
  }, []);

  return (
    <div className="discovery-panel">
      <div className="discovery-featured">
        <div className="discovery-section-title">Today&apos;s Featured Article</div>
        {featured ? (
          <>
            <div className="welcome-featured-title" onClick={() => onFeaturedClick(featured.title)}>
              {featured.title}
            </div>
            <p className="welcome-featured-extract">{featured.extract}</p>
            <p className="welcome-featured-meta">Source: Wikipedia Featured Articles</p>
          </>
        ) : (
          <p className="welcome-empty">Loading today&apos;s featured article…</p>
        )}
      </div>
      {suggestedTopics.length > 0 && (
        <div className="discovery-suggestions">
          <div className="discovery-section-title">Suggested for You</div>
          <div className="recent-chips">
            {suggestedTopics.map((t, i) => (
              <button key={i} className="recent-chip" onClick={() => onTopicClick(t)}>{t}</button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function Home() {
  const darkMode = useAppStore((s) => s.darkMode);
  const setDarkMode = useAppStore((s) => s.setDarkMode);
  const activeTopic = useAppStore((s) => s.activeTopic);
  const setGraphCache = useAppStore((s) => s.setGraphCache);
  const setPrefetchStatus = useAppStore((s) => s.setPrefetchStatus);
  const prefetchStatus = useAppStore((s) => s.prefetchStatus);
  const graphCache = useAppStore((s) => s.graphCache);

  const [blocks, setBlocks] = useState<ResponseBlock[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [showExpiryWarning, setShowExpiryWarning] = useState(false);
  const [showFirstLoad, setShowFirstLoad] = useState(false);
  const [pdfPreparing, setPdfPreparing] = useState(false);
  const [showBackToTop, setShowBackToTop] = useState(false);
  const chatPanelRef = useRef<ChatPanelHandle>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = contentRef.current;
    if (!el) return;
    const onScroll = () => setShowBackToTop(el.scrollTop > 400);
    el.addEventListener("scroll", onScroll);
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  // Suggestions derived from explore_further across all blocks, excluding already-explored topics
  const exploredSet = new Set(blocks.map(b => b.query.toLowerCase()));
  const suggestedTopics = [...new Set(
    blocks
      .filter(b => b.state === "done")
      .flatMap(b => [
        ...(b.section?.explore_further?.you_might_like ?? []),
        ...(b.section?.explore_further?.from_article ?? []),
      ])
  )].filter(t => !exploredSet.has(t.toLowerCase())).slice(0, 14);

  useEffect(() => {
    if (!localStorage.getItem("rabbitpedia_session_seen")) {
      setShowFirstLoad(true);
    }
  }, []);

  // Eager graph prefetch whenever activeTopic changes
  useEffect(() => {
    if (!activeTopic) return;
    const cached = graphCache[activeTopic];
    if ((cached && !isExpired(cached)) || prefetchStatus[activeTopic] === "loading") return;
    setPrefetchStatus(activeTopic, "loading");
    fetch(`http://localhost:8000/graph?topic=${encodeURIComponent(activeTopic)}`)
      .then(r => r.json())
      .then(data => {
        setGraphCache(activeTopic, data);
        setPrefetchStatus(activeTopic, "done");
      })
      .catch(() => setPrefetchStatus(activeTopic, "error"));
  }, [activeTopic, graphCache, prefetchStatus, setGraphCache, setPrefetchStatus]);

  function dismissFirstLoad() {
    localStorage.setItem("rabbitpedia_session_seen", "1");
    setShowFirstLoad(false);
  }

  const handleTopicClick = useCallback((topic: string) => {
    chatPanelRef.current?.runQuery(topic, { deep: false });
  }, []);

  return (
    <div className="page">
      <header className="wiki-header">
        <div className="wiki-header-inner">
          <button
            className="sidebar-toggle"
            onClick={() => setSidebarOpen(o => !o)}
            aria-label="Toggle sidebar"
            title="Toggle sidebar"
          >
            &#9776;
          </button>
          <h1><span className="logo-rabbit">Rabbit</span>Pedia</h1>
          <nav className="header-nav">
            <Link href="/" className="nav-link active">Home</Link>
            <Link href="/graph" className="nav-link">Knowledge Graph</Link>
            <Link href="/debate" className="nav-link">Debate</Link>
            <Link href="/perspectives" className="nav-link">Flip the Lens</Link>
            <Link href="/curiosity-path" className="nav-link">My Path</Link>
          </nav>
          <p className="tagline">The free encyclopedia that goes deeper</p>
          <div className="toolbar-actions">
            <button
              className="toolbar-icon"
              onClick={() => setDarkMode(!darkMode)}
              title={darkMode ? "Switch to light mode" : "Switch to dark mode"}
              aria-label="Toggle dark mode"
            >
              {darkMode ? "Light" : "Dark"}
            </button>
            <button
              className="toolbar-icon"
              onClick={() => setPdfPreparing(true)}
              disabled={blocks.length === 0 || pdfPreparing}
              title="Download conversation as PDF"
            >
              PDF
            </button>
          </div>
        </div>
      </header>

      <div className="main-layout">
        <Sidebar blocks={blocks} open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

        <div className="content-area" ref={contentRef}>
          <DiscoveryPanel
            suggestedTopics={suggestedTopics}
            onTopicClick={handleTopicClick}
            onFeaturedClick={handleTopicClick}
          />
          <ChatPanel
            ref={chatPanelRef}
            position="bottom"
            storageKey="home-blocks"
            onBlocksChange={setBlocks}
          />
        </div>
      </div>

      {showBackToTop && (
        <button
          className="back-to-top"
          onClick={() => contentRef.current?.scrollTo({ top: 0, behavior: "smooth" })}
          aria-label="Back to top"
        >
          ↑
        </button>
      )}
      {showExpiryWarning && <ExpiryWarning onDismiss={() => setShowExpiryWarning(false)} />}
      {showFirstLoad && <FirstLoadModal onDismiss={dismissFirstLoad} />}
      {pdfPreparing && <PdfPreparingModal />}
    </div>
  );
}

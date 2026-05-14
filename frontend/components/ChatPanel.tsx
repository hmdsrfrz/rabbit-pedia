"use client";

import { useState, useRef, useEffect, forwardRef, useImperativeHandle } from "react";
import { useAppStore } from "@/store";

export interface KeyConcept { term: string; definition: string; }
export interface Source { title: string; url: string; }
export interface ExploreFurther { from_article: string[]; you_might_like: string[]; }

export interface SectionData {
  heading: string;
  body: string;
  key_concepts: KeyConcept[] | null;
  did_you_know: string[];
  two_cents: string;
  sources: Source[];
  explore_further: ExploreFurther;
  image_url?: string;
  conversational?: boolean;
}

export interface ResponseBlock {
  id: string;
  query: string;
  state: "thinking" | "done";
  section: SectionData | null;
  deep: boolean;
  factMarks: Record<number, "up" | "down">;
  feedback?: "up" | "down";
  parentId?: string;
}

interface ChatPanelProps {
  position: "bottom" | "right";
  storageKey: string;
  initialQuery?: string;
  onNodeHighlight?: (topic: string) => void;
  onBlocksChange?: (blocks: ResponseBlock[]) => void;
}

export interface ChatPanelHandle {
  runQuery: (query: string, opts: { deep: boolean; replaceBlockId?: string; parentId?: string; skipTopicUpdate?: boolean }) => Promise<void>;
  getBlocks: () => ResponseBlock[];
  addExternalBlock: (query: string, section: SectionData) => void;
  addPendingBlock: (query: string) => string;
  resolveBlock: (blockId: string, section: SectionData) => void;
  scrollToLatest: () => void;
}

function BodyText({ text }: { text: string }) {
  return (
    <>
      {text.split("\n\n").filter(p => p.trim()).map((para, i) => (
        <p key={i} style={{ marginBottom: "0.8em" }}>{para.trim()}</p>
      ))}
    </>
  );
}

function ArticleInfobox({ heading, imageUrl }: { heading: string; imageUrl: string }) {
  return (
    <aside className="article-infobox">
      <div className="infobox-header">{heading}</div>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img className="infobox-image" src={imageUrl} alt={heading} />
      <div className="infobox-caption">{heading}</div>
    </aside>
  );
}

function WikiSection({
  block,
  onChipClick,
  onMarkFact,
  onFeedback,
  disabled,
}: {
  block: ResponseBlock;
  onChipClick: (topic: string, parentBlockId: string) => void;
  onMarkFact: (block: ResponseBlock, idx: number, fact: string, interested: boolean) => void;
  onFeedback: (block: ResponseBlock, rating: "up" | "down") => void;
  disabled: boolean;
}) {
  if (block.state === "thinking") {
    return (
      <div id={`section-${block.id}`} className="wiki-section">
        <div className="thinking-state">
          <span className="thinking-dots">{block.deep ? "Going deeper" : "Researching"}</span>
        </div>
      </div>
    );
  }

  const s = block.section!;

  if (s.conversational) {
    return (
      <div id={`section-${block.id}`} className="wiki-section conversational-section">
        <div className="conversational-bubble">
          <BodyText text={s.body} />
        </div>
      </div>
    );
  }

  return (
    <div id={`section-${block.id}`} className="wiki-section">
      <h2 className="section-heading">{s.heading}</h2>

      <div className="section-body">
        {s.image_url && <ArticleInfobox heading={s.heading} imageUrl={s.image_url} />}
        <BodyText text={s.body} />
      </div>

      {s.key_concepts && s.key_concepts.length > 0 && (
        <div className="subsection">
          <h3>Key Concepts</h3>
          <ul className="concept-list">
            {s.key_concepts.map((kc, i) => (
              <li key={i}><strong>{kc.term}</strong>: {kc.definition}</li>
            ))}
          </ul>
        </div>
      )}

      {s.did_you_know.length > 0 && (
        <div className="subsection did-you-know">
          <h3>Did You Know?</h3>
          <ul>
            {s.did_you_know.map((fact, i) => {
              const mark = block.factMarks[i];
              return (
                <li key={i} className="fact-row">
                  <span className="fact-text">{fact}</span>
                  <span className="fact-marks">
                    <button
                      className={`fact-mark${mark === "up" ? " fact-mark-active" : ""}`}
                      onClick={() => onMarkFact(block, i, fact, true)}
                    >Interested</button>
                    <button
                      className={`fact-mark${mark === "down" ? " fact-mark-active" : ""}`}
                      onClick={() => onMarkFact(block, i, fact, false)}
                    >Not interested</button>
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {s.two_cents && (
        <div className="subsection two-cents">
          <h3>RabbitPedia&apos;s Two Cents</h3>
          <BodyText text={s.two_cents} />
        </div>
      )}

      {s.sources.length > 0 && (
        <div className="subsection">
          <h3>Sources</h3>
          <ul className="sources-list">
            {s.sources.map((src, i) => (
              <li key={i}>
                <a href={src.url} target="_blank" rel="noopener noreferrer">{src.title}</a>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="explore-further">
        {s.explore_further.from_article.length > 0 && (
          <div className="chip-group">
            <span className="chip-label">From this article</span>
            <div className="chips">
              {s.explore_further.from_article.map((t, i) => (
                <button key={i} className="chip" disabled={disabled} onClick={() => onChipClick(t, block.id)}>{t}</button>
              ))}
            </div>
          </div>
        )}
        {s.explore_further.you_might_like.length > 0 && (
          <div className="chip-group">
            <span className="chip-label">You might like</span>
            <div className="chips">
              {s.explore_further.you_might_like.map((t, i) => (
                <button key={i} className="chip" disabled={disabled} onClick={() => onChipClick(t, block.id)}>{t}</button>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="response-actions">
        <span className="feedback-row">
          <span className="feedback-label">Was this helpful?</span>
          <button
            className={`feedback-btn${block.feedback === "up" ? " feedback-active" : ""}`}
            onClick={() => onFeedback(block, "up")}
          >yes</button>
          <button
            className={`feedback-btn${block.feedback === "down" ? " feedback-active" : ""}`}
            onClick={() => onFeedback(block, "down")}
          >no</button>
        </span>
      </div>
    </div>
  );
}

const ChatPanel = forwardRef<ChatPanelHandle, ChatPanelProps>(({
  position,
  storageKey,
  initialQuery,
  onNodeHighlight,
  onBlocksChange,
}, ref) => {
  const sessionId = useAppStore((s) => s.sessionId);
  const setActiveTopic = useAppStore((s) => s.setActiveTopic);

  const [blocks, setBlocksState] = useState<ResponseBlock[]>([]);
  const hydratedRef = useRef(false);

  useEffect(() => {
    if (hydratedRef.current) return;
    hydratedRef.current = true;
    try {
      const saved = sessionStorage.getItem(storageKey);
      if (saved) setBlocksState(JSON.parse(saved));
    } catch {}
  }, [storageKey]);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const loadingRef = useRef(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const initialQueryFiredRef = useRef(false);

  function setBlocks(updater: ResponseBlock[] | ((prev: ResponseBlock[]) => ResponseBlock[])) {
    setBlocksState(prev => {
      const next = typeof updater === "function" ? updater(prev) : updater;
      try { sessionStorage.setItem(storageKey, JSON.stringify(next)); } catch {}
      return next;
    });
  }

  useImperativeHandle(ref, () => ({
    runQuery,
    getBlocks: () => blocks,
    addExternalBlock: (query: string, section: SectionData) => {
      const block: ResponseBlock = {
        id: crypto.randomUUID(),
        query,
        state: "done",
        section,
        deep: false,
        factMarks: {},
      };
      setBlocks(prev => [...prev, block]);
    },
    addPendingBlock: (query: string) => {
      const id = crypto.randomUUID();
      setBlocks(prev => [...prev, {
        id, query, state: "thinking", section: null, deep: false, factMarks: {},
      }]);
      return id;
    },
    resolveBlock: (blockId: string, section: SectionData) => {
      setBlocks(prev => prev.map(b =>
        b.id === blockId ? { ...b, state: "done", section } : b
      ));
    },
    scrollToLatest: () => {
      requestAnimationFrame(() => {
        const el = scrollRef.current;
        if (!el) return;
        const last = el.lastElementChild as HTMLElement | null;
        if (last) last.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    },
  }));

  useEffect(() => {
    if (onBlocksChange) onBlocksChange(blocks);
  }, [blocks, onBlocksChange]);

  useEffect(() => {
    if (initialQuery && !initialQueryFiredRef.current) {
      initialQueryFiredRef.current = true;
      runQuery(initialQuery, { deep: false });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuery]);

  const prevBlockCountRef = useRef(0);
  useEffect(() => {
    if (!scrollRef.current) return;
    if (blocks.length > prevBlockCountRef.current) {
      prevBlockCountRef.current = blocks.length;
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [blocks]);

  async function runQuery(query: string, opts: { deep: boolean; replaceBlockId?: string; parentId?: string; skipTopicUpdate?: boolean }) {
    if (!query.trim() || loadingRef.current) return;
    loadingRef.current = true;
    setLoading(true);
    if (!opts.replaceBlockId) {
      setInput("");
      if (!opts.skipTopicUpdate) setActiveTopic(query.trim());
    }

    const blockId = opts.replaceBlockId ?? crypto.randomUUID();
    if (opts.replaceBlockId) {
      setBlocks(prev => prev.map(b =>
        b.id === blockId ? { ...b, state: "thinking", section: null, deep: opts.deep } : b
      ));
    } else {
      setBlocks(prev => [...prev, {
        id: blockId, query, state: "thinking", section: null, deep: opts.deep, factMarks: {},
        parentId: opts.parentId,
      }]);
    }

    try {
      const response = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: query, deep: opts.deep }),
      });

      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const event = JSON.parse(line.slice(6));
          if (event.type === "section") {
            setBlocks(prev => prev.map(b =>
              b.id === blockId ? { ...b, state: "done", section: event.content } : b
            ));
            if (event.content.heading && onNodeHighlight) {
              onNodeHighlight(event.content.heading);
            }
          }
        }
      }
    } catch {
      setBlocks(prev => prev.map(b =>
        b.id === blockId
          ? {
              ...b, state: "done", section: {
                heading: "Error",
                body: "Could not reach the backend. Make sure it is running on port 8000.",
                key_concepts: null,
                did_you_know: [],
                two_cents: "",
                sources: [],
                explore_further: { from_article: [], you_might_like: [] },
              }
            }
          : b
      ));
    } finally {
      loadingRef.current = false;
      setLoading(false);
    }
  }

  function submit(query: string) {
    return runQuery(query, { deep: false });
  }

  function chipSubmit(query: string, parentBlockId: string) {
    return runQuery(query, { deep: false, parentId: parentBlockId });
  }

  async function markFeedback(block: ResponseBlock, rating: "up" | "down") {
    setBlocks(prev => prev.map(b => b.id === block.id ? { ...b, feedback: rating } : b));
    try {
      await fetch("http://localhost:8000/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message_id: block.id, rating }),
      });
    } catch {}
  }

  async function markFact(block: ResponseBlock, idx: number, fact: string, interested: boolean) {
    setBlocks(prev => prev.map(b =>
      b.id === block.id
        ? { ...b, factMarks: { ...b.factMarks, [idx]: interested ? "up" : "down" } }
        : b
    ));
    try {
      await fetch("http://localhost:8000/interest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, fact, interested }),
      });
    } catch {}
  }

  return (
    <div className={`chat-panel chat-panel-${position}`}>
      <div className="chat-messages" ref={scrollRef}>
        {blocks.length === 0 && position === "bottom" && (
          <p className="empty-state">Ask anything — your rabbit hole starts here.</p>
        )}
        {blocks.map(block => (
          <div key={block.id} className="message-wrapper">
            {block.section?.conversational && (
              <div className="user-message">{block.query}</div>
            )}
            <WikiSection
              block={block}
              onChipClick={chipSubmit}
              onMarkFact={markFact}
              onFeedback={markFeedback}
              disabled={loading}
            />
          </div>
        ))}
        {loading && <div className="typing-indicator">RabbitPedia is thinking...</div>}
      </div>
      <div className="chat-input-area">
        <form onSubmit={e => { e.preventDefault(); submit(input); }}>
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Ask about any topic..."
            disabled={loading}
          />
          <button type="submit" disabled={loading || !input.trim()}>
            {loading ? "Thinking…" : "Search"}
          </button>
        </form>
      </div>
    </div>
  );
});

ChatPanel.displayName = "ChatPanel";

export default ChatPanel;

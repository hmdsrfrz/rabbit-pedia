"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useAppStore, isExpired } from "@/store";
import ChatPanel, { ChatPanelHandle } from "../../components/ChatPanel";

interface DebateSide {
  id: string;
  label: string;
  position: string;
  color: string;
}

interface DebateArgument {
  side_id: string;
  type: string;
  heading: string;
  content: string;
  targets: string | null;
  sources: string[];
}

interface DebateMeta {
  topic: string;
  question: string;
  context: string;
  red: DebateSide;
  blue: DebateSide;
  verdict: string;
}

function SourceChips({
  sources,
  onChipClick,
}: {
  sources: string[];
  onChipClick: (title: string) => void;
}) {
  if (!sources || sources.length === 0) return null;
  return (
    <div className="debate-source-chips">
      {sources.map((s, i) => (
        <button key={i} className="debate-source-chip" onClick={() => onChipClick(s)}>
          {s}
        </button>
      ))}
    </div>
  );
}

function ArgumentCard({
  round,
  side,
  onSourceClick,
}: {
  round: DebateArgument;
  side: "red" | "blue";
  onSourceClick: (title: string) => void;
}) {
  return (
    <div className={`debate-argument ${side}-arg`}>
      <div className="debate-argument-type">{round.type}</div>
      <div className="debate-argument-heading">{round.heading}</div>
      {round.targets && (
        <div className="debate-rebuttal-target">Attacking: {round.targets}</div>
      )}
      <div className="debate-argument-content">{round.content}</div>
      <SourceChips sources={round.sources} onChipClick={onSourceClick} />
    </div>
  );
}

function RoundRow({
  round,
  onSourceClick,
}: {
  round: DebateArgument;
  onSourceClick: (title: string) => void;
}) {
  const isRed = round.side_id === "red";
  return (
    <div className={`debate-round-row${round.type === "rebuttal" ? " rebuttal-row" : ""}`}>
      {isRed ? (
        <>
          <ArgumentCard round={round} side="red" onSourceClick={onSourceClick} />
          <div className="debate-empty-col" />
        </>
      ) : (
        <>
          <div className="debate-empty-col" />
          <ArgumentCard round={round} side="blue" onSourceClick={onSourceClick} />
        </>
      )}
    </div>
  );
}

function ChallengePairRow({
  question,
  red,
  blue,
  onSourceClick,
}: {
  question: string;
  red: DebateArgument;
  blue: DebateArgument;
  onSourceClick: (title: string) => void;
}) {
  return (
    <div className="debate-challenge-pair-wrapper">
      <div className="debate-challenge-question">
        <span className="debate-challenge-q-label">Challenge: </span>
        {question}
      </div>
      <div className="debate-round-row debate-challenge-pair">
        <ArgumentCard round={red} side="red" onSourceClick={onSourceClick} />
        <ArgumentCard round={blue} side="blue" onSourceClick={onSourceClick} />
      </div>
    </div>
  );
}

export default function DebatePage() {
  const activeTopic = useAppStore((s) => s.activeTopic);
  const darkMode = useAppStore((s) => s.darkMode);
  const setDarkMode = useAppStore((s) => s.setDarkMode);
  const debateCache = useAppStore((s) => s.debateCache);
  const setDebateCache = useAppStore((s) => s.setDebateCache);

  const [query, setQuery] = useState("");
  const [meta, setMeta] = useState<DebateMeta | null>(null);
  const [rounds, setRounds] = useState<DebateArgument[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [challenge, setChallenge] = useState("");
  const [challenging, setChallenging] = useState(false);
  const [challengeError, setChallengeError] = useState<string | null>(null);
  const [challengePairs, setChallengePairs] = useState<Array<{ question: string; red: DebateArgument; blue: DebateArgument }>>([]);

  const chatPanelRef = useRef<ChatPanelHandle>(null);
  const lastLoadedTopicRef = useRef("");

  useEffect(() => {
    if (!activeTopic || lastLoadedTopicRef.current === activeTopic) return;
    lastLoadedTopicRef.current = activeTopic;
    setQuery(activeTopic);
    const cached = debateCache[activeTopic];
    if (cached && !isExpired(cached)) {
      const { meta: cachedMeta, rounds: cachedRounds } = cached.data as { meta: DebateMeta; rounds: DebateArgument[] };
      setMeta(cachedMeta);
      setRounds(cachedRounds);
    } else {
      fetchDebate(activeTopic);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTopic]);

  async function fetchDebate(q: string) {
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    setMeta(null);
    setRounds([]);
    setChallengePairs([]);

    let finalMeta: DebateMeta | null = null;
    const finalRounds: DebateArgument[] = [];

    try {
      const resp = await fetch(`http://localhost:8000/debate?query=${encodeURIComponent(q)}`);
      if (!resp.body) throw new Error("No response body");

      const reader = resp.body.getReader();
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
          if (event.type === "meta") {
            finalMeta = event.content;
            setMeta(event.content);
            setLoading(false);
          } else if (event.type === "round") {
            finalRounds.push(event.content);
            setRounds(prev => [...prev, event.content]);
          } else if (event.type === "error") {
            setError(event.content);
            setLoading(false);
          }
        }
      }

      if (finalMeta && finalRounds.length > 0) {
        setDebateCache(q, { meta: finalMeta, rounds: finalRounds });
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not load the debate.");
      setLoading(false);
    }
  }

  function handleSourceClick(title: string) {
    chatPanelRef.current?.runQuery(title, { deep: false, skipTopicUpdate: true });
  }

  async function postChallenge(e: React.FormEvent) {
    e.preventDefault();
    if (!challenge.trim() || !meta || challenging) return;
    setChallenging(true);
    setChallengeError(null);
    const userChallenge = challenge;
    setChallenge("");

    try {
      const resp = await fetch("http://localhost:8000/debate/challenge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic: meta.topic,
          question: meta.question,
          red_position: meta.red.position,
          blue_position: meta.blue.position,
          challenge: userChallenge,
        }),
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail || "Challenge failed — please try again.");
      }
      const data = await resp.json();
      setChallengePairs(prev => [...prev, { question: userChallenge, red: data.red_reply, blue: data.blue_reply }]);
    } catch (err: unknown) {
      setChallengeError(err instanceof Error ? err.message : "Challenge failed — please try again.");
      setChallenge(userChallenge);
    } finally {
      setChallenging(false);
    }
  }

  const showVerdict = meta && rounds.length >= 14;

  return (
    <div className="debate-page">
      <header className="wiki-header">
        <div className="wiki-header-inner">
          <h1><span className="logo-rabbit">Rabbit</span>Pedia</h1>
          <nav className="header-nav">
            <Link href="/" className="nav-link">Home</Link>
            <Link href="/graph" className="nav-link">Knowledge Graph</Link>
            <Link href="/debate" className="nav-link active">Debate</Link>
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

      <div className="debate-layout">
        <div className="debate-body">
          <div className="debate-header-bar">
            <div className="debate-search-bar">
              <input
                type="text"
                placeholder="Enter a topic to debate..."
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={e => e.key === "Enter" && fetchDebate(query)}
                disabled={loading}
              />
              <button onClick={() => fetchDebate(query)} disabled={!!(loading || !query.trim())} suppressHydrationWarning>
                {loading ? "Preparing..." : "Start Debate"}
              </button>
            </div>
            {meta && (
              <>
                <div className="debate-question">{meta.question}</div>
                <div className="debate-context">{meta.context}</div>
              </>
            )}
          </div>

          {loading && <div className="debate-loading">Researching the topic…</div>}
          {error && <div className="debate-error" style={{ color: "var(--debate-red)" }}>{error}</div>}
          {!loading && !error && !meta && (
            <div className="debate-loading" style={{ color: "var(--text-faint)" }}>
              Enter a topic above to explore its most contested questions.
            </div>
          )}

          {meta && (
            <>
              <div className="debate-sides-header">
                <div className="debate-side-label red">
                  {meta.red.label}
                  <div className="debate-side-position">{meta.red.position}</div>
                </div>
                <div className="debate-side-label blue">
                  {meta.blue.label}
                  <div className="debate-side-position">{meta.blue.position}</div>
                </div>
              </div>

              <div className="debate-rounds">
                {rounds.map((round, i) => (
                  <RoundRow
                    key={i}
                    round={round}
                    onSourceClick={handleSourceClick}
                  />
                ))}

                {showVerdict && (
                  <div className="debate-verdict">
                    <div className="debate-verdict-label">The Evidence Suggests</div>
                    <div className="debate-verdict-text">{meta.verdict}</div>
                  </div>
                )}

                {challengePairs.length > 0 && (
                  <>
                    <div className="debate-challenge-divider">Challenges</div>
                    {challengePairs.map((pair, i) => (
                      <ChallengePairRow
                        key={i}
                        question={pair.question}
                        red={pair.red}
                        blue={pair.blue}
                        onSourceClick={handleSourceClick}
                      />
                    ))}
                  </>
                )}
              </div>
            </>
          )}
        </div>

        <div className="debate-side-panel debate-side-panel-open">
          <ChatPanel
            ref={chatPanelRef}
            position="right"
            storageKey="debate-side-blocks"
          />
        </div>
      </div>

      {meta && (
        <div className="debate-challenge-bar">
          {challengeError && (
            <div style={{ maxWidth: 800, margin: "0 auto 6px", color: "var(--color-red, #c0392b)", fontSize: 12 }}>
              {challengeError}
            </div>
          )}
          <form onSubmit={postChallenge} style={{ display: "flex", gap: 8, maxWidth: 800, margin: "0 auto" }}>
            <input
              type="text"
              placeholder="Challenge a side — both Red and Blue will respond directly"
              value={challenge}
              onChange={e => setChallenge(e.target.value)}
              disabled={challenging}
              style={{
                flex: 1, padding: "7px 12px", border: "1px solid var(--border-strong)",
                borderRadius: 2, fontFamily: "Arial, sans-serif", fontSize: 13,
                background: "var(--bg-input)", color: "var(--text-body)", outline: "none",
              }}
            />
            <button
              type="submit"
              disabled={challenging || !challenge.trim()}
              style={{
                padding: "7px 16px", background: "var(--text-link)", color: "#fff",
                border: "none", borderRadius: 2, fontFamily: "Arial, sans-serif",
                fontSize: 13, fontWeight: "bold", cursor: "pointer",
              }}
            >
              {challenging ? "Thinking..." : "Challenge"}
            </button>
          </form>
        </div>
      )}
    </div>
  );
}

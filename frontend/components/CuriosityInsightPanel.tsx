"use client";

import Link from "next/link";

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

interface CuriosityInsightPanelProps {
  insight: CuriosityInsight;
  selectedNode: PathNode | null;
  previousTransition: string | null;
  onBackToProfile: () => void;
}

const DEPTH_COLORS: Record<string, string> = {
  "surface skimmer": "#e67e22",
  "focused diver": "#2980b9",
  "wide wanderer": "#8e44ad",
  "deep obsessive": "#c0392b"
};

export default function CuriosityInsightPanel({ insight, selectedNode, previousTransition, onBackToProfile }: CuriosityInsightPanelProps) {
  if (selectedNode) {
    return (
      <div className="insight-panel node-selected">
        <button className="back-btn" onClick={onBackToProfile}>← Back to profile</button>
        
        <h2 className="node-title">{selectedNode.title}</h2>
        <span className="order-badge">Stop #{selectedNode.order}</span>

        <div className="info-section">
          <label>WHAT IT IS</label>
          <p>{selectedNode.summary}</p>
        </div>

        <div className="info-section">
          <label>WHY YOU WENT HERE</label>
          <p>{selectedNode.why_interesting}</p>
        </div>

        {previousTransition && (
          <div className="info-section">
            <label>HOW YOU GOT HERE</label>
            <p>{previousTransition}</p>
          </div>
        )}

        <Link href={`/?q=${encodeURIComponent(selectedNode.title)}`} className="explore-btn">
          Explore again →
        </Link>

        <style jsx>{`
          .insight-panel { padding: 30px; background: var(--bg-content); border-left: 1px solid var(--wp-border); height: 100%; display: flex; flex-direction: column; }
          .back-btn { background: none; border: none; color: var(--text-link); cursor: pointer; padding: 0; margin-bottom: 25px; text-align: left; font-size: 14px; }
          .node-title { font-family: var(--wp-serif); font-size: 28px; margin-bottom: 10px; }
          .order-badge { display: inline-block; padding: 4px 12px; background: var(--border-faint); border-radius: 15px; font-size: 12px; font-weight: bold; margin-bottom: 30px; }
          .info-section { margin-bottom: 25px; }
          .info-section label { display: block; font-size: 11px; font-weight: bold; color: var(--text-faint); margin-bottom: 8px; letter-spacing: 0.05em; }
          .info-section p { font-size: 15px; line-height: 1.6; }
          .explore-btn { margin-top: auto; display: block; text-align: center; padding: 12px; background: var(--text-link); color: #fff; text-decoration: none; border-radius: 4px; font-weight: bold; }
        `}</style>
      </div>
    );
  }

  const depthColor = DEPTH_COLORS[insight.rabbit_hole_depth] || "#72777d";

  return (
    <div className="insight-panel profile-view">
      <h3 className="panel-heading">YOUR CURIOSITY PROFILE</h3>
      
      <div className="depth-badge" style={{ backgroundColor: depthColor }}>
        {insight.rabbit_hole_depth.toUpperCase()}
      </div>

      <div className="pattern-quote">
        &ldquo;{insight.pattern}&rdquo;
      </div>

      <div className="info-section">
        <label>HIDDEN THEME</label>
        <p className="theme-text">"{insight.theme}"</p>
      </div>

      <div className="info-section">
        <label>MOST UNEXPECTED JUMP</label>
        <p>{insight.most_unexpected_jump}</p>
      </div>

      <div className="info-section next-rec">
        <label>YOU MIGHT LOVE NEXT</label>
        <p className="rec-topic">{insight.next_recommendation}</p>
        <Link href={`/?q=${encodeURIComponent(insight.next_recommendation)}`} className="rec-link">
          Explore →
        </Link>
      </div>

      <style jsx>{`
        .insight-panel { padding: 30px; background: var(--bg-content); border-left: 1px solid var(--wp-border); height: 100%; overflow-y: auto; }
        .panel-heading { font-size: 13px; font-weight: bold; color: var(--text-faint); margin-bottom: 25px; letter-spacing: 0.1em; }
        .depth-badge { display: inline-block; padding: 4px 12px; color: #fff; border-radius: 4px; font-size: 11px; font-weight: bold; margin-bottom: 25px; }
        .pattern-quote { font-family: var(--wp-serif); font-size: 24px; font-style: italic; line-height: 1.4; margin-bottom: 40px; color: var(--text-body); }
        .info-section { margin-bottom: 30px; }
        .info-section label { display: block; font-size: 11px; font-weight: bold; color: var(--text-faint); margin-bottom: 10px; letter-spacing: 0.05em; }
        .theme-text { font-size: 18px; font-weight: bold; font-family: var(--wp-serif); }
        .rec-topic { font-size: 18px; font-family: var(--wp-serif); margin-bottom: 10px; }
        .rec-link { color: var(--text-link); text-decoration: none; font-weight: bold; font-size: 14px; }
        .next-rec { background: var(--bg-page); padding: 20px; border-radius: 8px; border: 1px solid var(--wp-border); }
      `}</style>
    </div>
  );
}

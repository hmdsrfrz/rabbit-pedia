"use client";

import { useEffect, useRef } from "react";
import * as d3 from "d3";

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

interface CuriosityPathGraphProps {
  nodes: PathNode[];
  edges: PathEdge[];
  onNodeClick: (node: PathNode) => void;
  onEdgeHover: (edge: PathEdge | null) => void;
  darkMode: boolean;
}

export default function CuriosityPathGraph({ nodes, edges, onNodeClick, onEdgeHover, darkMode }: CuriosityPathGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return;

    const width = svgRef.current.clientWidth || 800;
    const height = svgRef.current.clientHeight || 500;
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const g = svg.append("g").attr("transform", "translate(50, 50)");

    // Arrange nodes in a flowing path (sine wave or similar)
    const innerWidth = width - 100;
    const innerHeight = height - 100;
    
    const xPadding = innerWidth / (nodes.length - 1 || 1);
    
    const points: [number, number][] = nodes.map((n, i) => {
        const x = i * xPadding;
        const y = innerHeight / 2 + Math.sin(i * 1.5) * (innerHeight / 3);
        return [x, y];
    });

    const lineGenerator = (d3.line as any)().curve(d3.curveBasis);
    const pathData = lineGenerator(points);

    // sequential river path
    g.append("path")
      .attr("d", pathData)
      .attr("fill", "none")
      .attr("stroke", "url(#path-gradient)")
      .attr("stroke-width", 6)
      .attr("stroke-linecap", "round")
      .attr("stroke-linejoin", "round")
      .attr("opacity", 0.8);

    // Gradient for the path
    const defs = svg.append("defs");
    const gradient = defs.append("linearGradient")
      .attr("id", "path-gradient")
      .attr("x1", "0%").attr("y1", "0%")
      .attr("x2", "100%").attr("y2", "0%");
    
    gradient.append("stop").attr("offset", "0%").attr("stop-color", "#f6c90e");
    gradient.append("stop").attr("offset", "100%").attr("stop-color", "#3366cc");

    // Thematic edges (dashed lines)
    const thematicEdges = edges.filter(e => {
        // Only thematic if not consecutive
        const sIdx = nodes.findIndex(n => n.id === e.source);
        const tIdx = nodes.findIndex(n => n.id === e.target);
        return Math.abs(sIdx - tIdx) > 1;
    });

    g.selectAll(".thematic-edge")
      .data(thematicEdges)
      .join("path")
      .attr("class", "thematic-edge")
      .attr("d", (d: any) => {
          const s = points[nodes.findIndex(n => n.id === d.source)];
          const t = points[nodes.findIndex(n => n.id === d.target)];
          const midX = (s[0] + t[0]) / 2;
          const midY = Math.min(s[1], t[1]) - 50;
          return `M ${s[0]} ${s[1]} Q ${midX} ${midY} ${t[0]} ${t[1]}`;
      })
      .attr("fill", "none")
      .attr("stroke", "#a2a9b1")
      .attr("stroke-width", 1.5)
      .attr("stroke-dasharray", "4,4")
      .attr("opacity", 0.6)
      .on("mouseenter", (_e: any, d: any) => onEdgeHover(d))
      .on("mouseleave", () => onEdgeHover(null));

    // Nodes
    const nodeGroups = g.selectAll(".node-group")
      .data(nodes)
      .join("g")
      .attr("class", "node-group")
      .attr("transform", (_d: any, i: any) => `translate(${points[i][0]}, ${points[i][1]})`)
      .style("cursor", "pointer")
      .on("click", (_e: any, d: any) => onNodeClick(d));

    const midNodeFill = darkMode ? "#2a3a5c" : "#fff";
    const labelColor = darkMode ? "#f8f9fa" : "#202122";
    const metaLabelColor = darkMode ? "#adb5bd" : "#72777d";

    nodeGroups.append("circle")
      .attr("r", (_d: any, i: any) => (i === 0 || i === nodes.length - 1) ? 24 : 18)
      .attr("fill", (_d: any, i: any) => i === 0 ? "#f6c90e" : (i === nodes.length - 1 ? "#3366cc" : midNodeFill))
      .attr("stroke", "#3366cc")
      .attr("stroke-width", 3);

    nodeGroups.append("text")
      .attr("dy", (_d: any, i: any) => (i === 0 || i === nodes.length - 1) ? 40 : 35)
      .attr("text-anchor", "middle")
      .attr("font-size", "12px")
      .attr("font-weight", "bold")
      .attr("fill", labelColor)
      .text((d: any) => d.title);

    // Labels for START and NOW
    nodeGroups.filter((_d: any, i: any) => i === 0).append("text")
      .attr("dy", -35)
      .attr("text-anchor", "middle")
      .attr("font-size", "10px")
      .attr("font-weight", "bold")
      .attr("fill", metaLabelColor)
      .text("START");

    nodeGroups.filter((_d: any, i: any) => i === nodes.length - 1).append("text")
      .attr("dy", -35)
      .attr("text-anchor", "middle")
      .attr("font-size", "10px")
      .attr("font-weight", "bold")
      .attr("fill", "#3366cc")
      .text("NOW");

  }, [nodes, edges, onNodeClick, onEdgeHover, darkMode]);

  return (
    <div className="graph-container" style={{ width: "100%", height: "100%", position: "relative" }}>
      <svg ref={svgRef} style={{ width: "100%", height: "100%" }}></svg>
    </div>
  );
}

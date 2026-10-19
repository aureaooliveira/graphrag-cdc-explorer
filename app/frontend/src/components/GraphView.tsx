import React, { useRef, useMemo, useCallback, useState, useEffect } from "react";
import ForceGraph2D from "react-force-graph-2d";
import type { GraphData, GraphHighlight, GraphNode } from "../types/graph";
import { colorFor, communityColor } from "@/lib/colors";

interface GraphViewProps {
  data: GraphData | null;
  colorMode: "type" | "community";
  communityLevel: number;
  selectedTypes: string[];
  searchQuery: string;
  onNodeClick: (node: GraphNode) => void;
  /** nós e relações a destacar (os demais ficam esmaecidos) */
  highlight?: GraphHighlight | null;
  /** a tela está visível (usado para enquadrar o destaque ao abrir a aba) */
  active?: boolean;
  width?: number;
  height?: number;
}

export const GraphView: React.FC<GraphViewProps> = ({
  data,
  colorMode,
  communityLevel,
  selectedTypes,
  searchQuery,
  onNodeClick,
  highlight,
  active = true,
  width,
  height,
}) => {
  const fgRef = useRef<any>(null);
  const [windowSize, setWindowSize] = useState({ width: window.innerWidth, height: window.innerHeight });

  useEffect(() => {
    const handleResize = () => setWindowSize({ width: window.innerWidth, height: window.innerHeight });
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Filter data based on selected types
  const filteredData = useMemo(() => {
    if (!data) return { nodes: [], edges: [], links: [] };

    let nodes = data.nodes;
    if (selectedTypes.length > 0) {
      nodes = nodes.filter((n) => selectedTypes.includes(n.type));
    }

    const nodeIds = new Set(nodes.map((n) => n.id));
    const edges = data.edges.filter(
      (e) => nodeIds.has(e.source as any) && nodeIds.has(e.target as any)
    );

    // react-force-graph expects "links" instead of "edges" and it mutates the object
    const graphNodes = nodes.map(n => ({ ...n }));
    const graphLinks = edges.map(e => ({ ...e, source: e.source, target: e.target }));

    return { nodes: graphNodes, edges, links: graphLinks };
  }, [data, selectedTypes]);

  // Handle Search Query Focus
  useEffect(() => {
    if (searchQuery && fgRef.current && filteredData.nodes.length > 0) {
      const lowerQuery = searchQuery.toLowerCase();
      const node = filteredData.nodes.find((n: any) => n.label.toLowerCase().includes(lowerQuery));
      if (node && (node as any).x !== undefined) {
        fgRef.current.centerAt((node as any).x, (node as any).y, 1000);
        fgRef.current.zoom(4, 2000);
      }
    }
  }, [searchQuery, filteredData]);

  // Enquadra os nós destacados quando o destaque muda ou a aba é aberta.
  useEffect(() => {
    if (!highlight || !active || !fgRef.current) return;
    const t = setTimeout(
      () => fgRef.current?.zoomToFit(800, 60, (n: any) => highlight.nodeIds.has(n.id)),
      400,
    );
    return () => clearTimeout(t);
  }, [highlight, active, width, height]);

  const linkKeyOf = (link: any) => {
    const s = typeof link.source === "object" ? link.source.id : link.source;
    const t = typeof link.target === "object" ? link.target.id : link.target;
    return `${s}|${t}`;
  };

  const getNodeColor = useCallback((node: any) => {
    if (highlight && !highlight.nodeIds.has(node.id)) return "rgba(180, 180, 180, 0.18)";
    if (colorMode === "type") {
      return colorFor(node.type || "unknown");
    } else {
      const comm = node.communities?.find((c: any) => c.level === communityLevel);
      return comm ? communityColor(comm.community_id) : "#cccccc";
    }
  }, [colorMode, communityLevel, highlight]);

  const paintNode = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const label = node.label;
    const fontSize = 12 / globalScale;
    ctx.font = `${fontSize}px Sans-Serif`;
    const degree = node.degree || 1;
    const radius = Math.max(2, Math.sqrt(degree) * 2);

    ctx.beginPath();
    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);
    ctx.fillStyle = getNodeColor(node);
    ctx.fill();

    // Highlight border if it matches search
    if (searchQuery && label.toLowerCase().includes(searchQuery.toLowerCase())) {
        ctx.lineWidth = 2 / globalScale;
        ctx.strokeStyle = "red";
        ctx.stroke();
    }

    // Rótulos: com destaque ativo, só dos nós destacados (e já com pouco zoom).
    const highlighted = highlight?.nodeIds.has(node.id);
    if (highlight ? highlighted && globalScale > 0.6 : globalScale > 1.5) {
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = 'rgba(30, 30, 30, 0.85)';
      ctx.fillText(label, node.x, node.y + radius + fontSize);
    }
  }, [getNodeColor, searchQuery, highlight]);

  return (
    <div className="w-full h-full bg-background relative" style={{ minHeight: "600px" }}>
      {filteredData.nodes.length === 0 ? (
        <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
          {data ? "Nenhuma entidade encontrada para os filtros aplicados." : "Carregando grafo..."}
        </div>
      ) : (
        <ForceGraph2D
          ref={fgRef}
          width={width || windowSize.width}
          height={height || windowSize.height}
          graphData={filteredData}
          nodeLabel={(node: any) => `
            <div class="bg-popover text-popover-foreground p-2 rounded shadow-md border border-border text-sm max-w-xs">
                <strong>${node.label}</strong><br/>
                <span class="text-xs text-muted-foreground">Tipo: ${node.type} | Grau: ${node.degree}</span><br/>
                <p class="mt-1 text-xs truncate whitespace-normal">${node.description}</p>
            </div>
          `}
          linkLabel={(link: any) => `
            <div class="bg-popover text-popover-foreground p-1 rounded shadow text-xs">
                ${link.description || "Relacionamento"} (Peso: ${link.weight || 1})
            </div>
          `}
          nodeCanvasObject={paintNode}
          nodeRelSize={6}
          onNodeClick={(node: any) => {
            fgRef.current.centerAt(node.x, node.y, 1000);
            fgRef.current.zoom(4, 2000);
            onNodeClick(node as GraphNode);
          }}
          linkColor={(link: any) =>
            highlight
              ? highlight.linkKeys.has(linkKeyOf(link))
                ? "rgba(220, 38, 38, 0.55)"
                : "rgba(150, 150, 150, 0.04)"
              : "rgba(150, 150, 150, 0.2)"
          }
          linkWidth={(link: any) =>
            highlight && highlight.linkKeys.has(linkKeyOf(link)) ? 1.5 : Math.min(3, Math.max(0.5, link.weight || 1))
          }
          cooldownTicks={100}
          d3AlphaDecay={0.02}
        />
      )}
    </div>
  );
};

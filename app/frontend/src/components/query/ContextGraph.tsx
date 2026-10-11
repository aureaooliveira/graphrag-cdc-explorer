import React, { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { Maximize2 } from "lucide-react";
import { Button } from "../ui/button";
import { colorFor } from "@/lib/colors";
import type { GraphData, GraphNode } from "../../types/graph";
import type { ContextHighlight } from "@/lib/highlight";

const MAX_NODES = 250;

interface ContextGraphProps {
  graph: GraphData;
  highlight: ContextHighlight;
  onOpenFullGraph: () => void;
}

/** Subgrafo com as entidades e relações usadas como contexto de uma consulta. */
export const ContextGraph: React.FC<ContextGraphProps> = ({ graph, highlight, onOpenFullGraph }) => {
  const fgRef = useRef<any>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(600);
  const [selected, setSelected] = useState<GraphNode | null>(null);

  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWidth(e.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const { data, truncated, types } = useMemo(() => {
    let nodes = graph.nodes.filter((n) => highlight.nodeIds.has(n.id));
    const truncated = nodes.length > MAX_NODES;
    if (truncated) nodes = [...nodes].sort((a, b) => b.degree - a.degree).slice(0, MAX_NODES);
    const ids = new Set(nodes.map((n) => n.id));
    const links = graph.edges
      .filter((e) => ids.has(e.source) && ids.has(e.target) && highlight.linkKeys.has(`${e.source}|${e.target}`))
      .map((e) => ({ ...e }));
    const types = [...new Set(nodes.map((n) => n.type))].sort();
    return { data: { nodes: nodes.map((n) => ({ ...n })), links }, truncated, types };
  }, [graph, highlight]);

  return (
    <div className="space-y-2">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          {data.nodes.length} entidade(s), {data.links.length} relação(ões). {highlight.basis}
          {truncated && ` Exibindo as ${MAX_NODES} entidades mais conectadas.`}
          {highlight.missing > 0 && ` ${highlight.missing} entidade(s) do contexto não foram localizadas no grafo.`}
          {" "}Passe o mouse sobre um nó para ver o nome, clique para ver a descrição e use a roda do mouse para aproximar.
        </p>
        <Button variant="outline" size="sm" onClick={onOpenFullGraph}>
          <Maximize2 className="mr-1 h-3.5 w-3.5" /> Ver no grafo completo
        </Button>
      </div>
      <div ref={boxRef} className="relative h-[420px] overflow-hidden rounded border bg-background">
        <ForceGraph2D
          ref={fgRef}
          width={width}
          height={420}
          graphData={data}
          cooldownTicks={120}
          onEngineStop={() => fgRef.current?.zoomToFit(400, 30)}
          nodeLabel={(n: any) => `${n.label} (${n.type})`}
          linkColor={() => "rgba(120,120,120,0.35)"}
          linkLabel={(l: any) => l.description}
          onNodeClick={(n: any) => setSelected(n as GraphNode)}
          nodeCanvasObject={(node: any, ctx, scale) => {
            const r = Math.max(3, Math.sqrt(node.degree || 1) * 1.6);
            ctx.beginPath();
            ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
            ctx.fillStyle = colorFor(node.type || "unknown");
            ctx.fill();
            if (selected?.id === node.id) {
              ctx.lineWidth = 2 / scale;
              ctx.strokeStyle = "#111";
              ctx.stroke();
            }
            if (scale > 1.8 || data.nodes.length <= 15) {
              const fontSize = 11 / scale;
              ctx.font = `${fontSize}px Sans-Serif`;
              ctx.textAlign = "center";
              ctx.textBaseline = "top";
              ctx.fillStyle = "rgba(30,30,30,0.85)";
              ctx.fillText(node.label, node.x, node.y + r + 1);
            }
          }}
        />
        <div className="pointer-events-none absolute bottom-2 left-2 flex max-w-[70%] flex-wrap gap-x-3 gap-y-1 rounded bg-background/90 p-1.5 text-[10px]">
          {types.map((t) => (
            <span key={t} className="flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: colorFor(t) }} />
              {t}
            </span>
          ))}
        </div>
      </div>
      {selected && (
        <div className="rounded border bg-muted/40 p-2 text-xs">
          <div className="font-semibold">
            {selected.label} <span className="font-normal text-muted-foreground">· {selected.type} · grau {selected.degree}</span>
          </div>
          <p className="mt-1 whitespace-pre-wrap text-muted-foreground">{selected.description}</p>
        </div>
      )}
    </div>
  );
};

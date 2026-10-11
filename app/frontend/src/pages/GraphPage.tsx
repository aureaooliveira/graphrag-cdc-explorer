import React, { useEffect, useRef, useState } from "react";
import { useGraphData } from "../hooks/useGraphData";
import { GraphView } from "../components/GraphView";
import { FiltersPanel } from "../components/FiltersPanel";
import { EntityDetailsPanel } from "../components/EntityDetailsPanel";
import { Legend } from "../components/Legend";
import type { GraphNode } from "../types/graph";

/** Visualização do grafo de conhecimento (tela original da aplicação). */
export const GraphPage: React.FC = () => {
  const { graphData, meta, loading, error } = useGraphData();
  const [colorMode, setColorMode] = useState<"type" | "community">("type");
  const [communityLevel, setCommunityLevel] = useState<number>(0);
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 800, height: 600 });

  useEffect(() => {
    if (meta && selectedTypes.length === 0) {
      setSelectedTypes(meta.entity_types);
      if (meta.community_levels.length > 0) setCommunityLevel(meta.community_levels[0]);
    }
  }, [meta]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) =>
      setSize({ width: entry.contentRect.width, height: entry.contentRect.height }),
    );
    ro.observe(el);
    return () => ro.disconnect();
  }, [loading]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
          <p className="text-muted-foreground">Carregando dados do grafo...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="max-w-md rounded-lg border border-destructive bg-destructive/10 p-6 text-center">
          <h2 className="mb-2 text-lg font-semibold text-destructive">Erro ao carregar dados</h2>
          <p className="text-sm text-muted-foreground">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative h-full w-full overflow-hidden">
      <FiltersPanel
        meta={meta}
        colorMode={colorMode}
        setColorMode={setColorMode}
        communityLevel={communityLevel}
        setCommunityLevel={setCommunityLevel}
        selectedTypes={selectedTypes}
        setSelectedTypes={setSelectedTypes}
        searchQuery={searchQuery}
        setSearchQuery={setSearchQuery}
      />
      <Legend meta={meta} colorMode={colorMode} />
      <GraphView
        data={graphData}
        colorMode={colorMode}
        communityLevel={communityLevel}
        selectedTypes={selectedTypes}
        searchQuery={searchQuery}
        onNodeClick={(node) => setSelectedNode(node)}
        width={size.width}
        height={size.height}
      />
      <EntityDetailsPanel node={selectedNode} onClose={() => setSelectedNode(null)} />
    </div>
  );
};

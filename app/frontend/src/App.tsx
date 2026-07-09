import React, { useState, useEffect } from "react";
import { useGraphData } from "./hooks/useGraphData";
import { GraphView } from "./components/GraphView";
import { FiltersPanel } from "./components/FiltersPanel";
import { EntityDetailsPanel } from "./components/EntityDetailsPanel";
import { Legend } from "./components/Legend";
import { GraphNode } from "./types/graph";

function App() {
  const { graphData, meta, loading, error } = useGraphData();

  const [colorMode, setColorMode] = useState<"type" | "community">("type");
  const [communityLevel, setCommunityLevel] = useState<number>(0);
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  useEffect(() => {
    if (meta && selectedTypes.length === 0) {
      setSelectedTypes(meta.entity_types);
      if (meta.community_levels.length > 0) {
        setCommunityLevel(meta.community_levels[0]);
      }
    }
  }, [meta]);

  if (loading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-background text-foreground">
        <div className="flex flex-col items-center gap-4">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
          <p className="text-muted-foreground">Carregando dados do grafo...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-background text-foreground">
        <div className="max-w-md p-6 bg-destructive/10 border border-destructive rounded-lg text-center">
          <h2 className="text-lg font-semibold text-destructive mb-2">Erro ao carregar dados</h2>
          <p className="text-sm text-muted-foreground">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-background text-foreground">
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
      />

      <EntityDetailsPanel 
        node={selectedNode} 
        onClose={() => setSelectedNode(null)} 
      />
    </div>
  );
}

export default App;

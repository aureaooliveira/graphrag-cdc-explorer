import React from "react";
import { MetaData } from "../types/graph";
import { Card, CardContent } from "./ui/card";
import { Badge } from "./ui/badge";

interface FiltersPanelProps {
  meta: MetaData | null;
  colorMode: "type" | "community";
  setColorMode: (mode: "type" | "community") => void;
  communityLevel: number;
  setCommunityLevel: (level: number) => void;
  selectedTypes: string[];
  setSelectedTypes: (types: string[]) => void;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
}

export const FiltersPanel: React.FC<FiltersPanelProps> = ({
  meta,
  colorMode,
  setColorMode,
  communityLevel,
  setCommunityLevel,
  selectedTypes,
  setSelectedTypes,
  searchQuery,
  setSearchQuery,
}) => {
  if (!meta) return null;

  const toggleType = (type: string) => {
    if (selectedTypes.includes(type)) {
      setSelectedTypes(selectedTypes.filter((t) => t !== type));
    } else {
      setSelectedTypes([...selectedTypes, type]);
    }
  };

  return (
    <Card className="absolute top-4 left-4 w-72 z-10 shadow-lg bg-background/95 backdrop-blur">
      <CardContent className="p-4 space-y-4">
        
        <div>
          <label className="text-xs font-semibold uppercase text-muted-foreground mb-1 block">Buscar</label>
          <input 
            type="text" 
            placeholder="Nome da entidade..." 
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <div className="border-t pt-3">
          <label className="text-xs font-semibold uppercase text-muted-foreground mb-2 block">Visualização (Cores)</label>
          <div className="flex gap-2">
            <button 
              className={`flex-1 text-xs py-1.5 rounded border transition-colors ${colorMode === 'type' ? 'bg-primary text-primary-foreground' : 'bg-muted'}`}
              onClick={() => setColorMode("type")}
            >
              Por Tipo
            </button>
            <button 
              className={`flex-1 text-xs py-1.5 rounded border transition-colors ${colorMode === 'community' ? 'bg-primary text-primary-foreground' : 'bg-muted'}`}
              onClick={() => setColorMode("community")}
            >
              Por Comunidade
            </button>
          </div>
        </div>

        {colorMode === "community" && (
          <div className="border-t pt-3 animate-in fade-in">
            <label className="text-xs font-semibold uppercase text-muted-foreground mb-1 block">Nível de Comunidade</label>
            <select 
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
              value={communityLevel}
              onChange={(e) => setCommunityLevel(Number(e.target.value))}
            >
              {meta.community_levels.map((lvl) => (
                <option key={lvl} value={lvl}>Nível {lvl}</option>
              ))}
            </select>
          </div>
        )}

        <div className="border-t pt-3">
          <label className="text-xs font-semibold uppercase text-muted-foreground mb-2 block">
            Filtros por Tipo ({selectedTypes.length}/{meta.entity_types.length})
          </label>
          <div className="flex flex-wrap gap-1.5">
            {meta.entity_types.map((type) => {
              const isSelected = selectedTypes.includes(type);
              return (
                <Badge
                  key={type}
                  variant={isSelected ? "default" : "outline"}
                  className="cursor-pointer hover:bg-primary/80 transition-colors text-[10px] px-1.5 py-0"
                  onClick={() => toggleType(type)}
                >
                  {type}
                </Badge>
              );
            })}
          </div>
          {selectedTypes.length < meta.entity_types.length && (
            <button 
              className="text-xs text-primary hover:underline mt-2" 
              onClick={() => setSelectedTypes(meta.entity_types)}
            >
              Mostrar Todos
            </button>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

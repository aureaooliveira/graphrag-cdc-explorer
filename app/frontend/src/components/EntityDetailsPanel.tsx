import React from "react";
import { GraphNode } from "../types/graph";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { X } from "lucide-react";

interface EntityDetailsPanelProps {
  node: GraphNode | null;
  onClose: () => void;
}

export const EntityDetailsPanel: React.FC<EntityDetailsPanelProps> = ({ node, onClose }) => {
  if (!node) return null;

  // Group communities by level
  const sortedCommunities = [...(node.communities || [])].sort((a, b) => a.level - b.level);

  return (
    <div className="absolute top-0 right-0 h-full w-96 bg-card border-l shadow-xl overflow-y-auto z-10 flex flex-col animate-in slide-in-from-right-10">
      <div className="flex items-center justify-between p-4 border-b bg-muted/30 sticky top-0 backdrop-blur">
        <h2 className="text-lg font-semibold truncate">Detalhes da Entidade</h2>
        <Button variant="ghost" size="icon" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="p-4 space-y-6">
        <div>
          <div className="flex items-start justify-between mb-2">
            <h3 className="text-xl font-bold leading-tight">{node.label}</h3>
          </div>
          <div className="flex gap-2 mb-4">
            <Badge variant="default">{node.type}</Badge>
            <Badge variant="outline">Grau: {node.degree}</Badge>
          </div>
          <p className="text-sm text-muted-foreground whitespace-pre-wrap">{node.description}</p>
        </div>

        {sortedCommunities.length > 0 && (
          <div className="space-y-3">
            <h4 className="text-sm font-semibold uppercase text-muted-foreground tracking-wider">
              Resumos de Comunidades
            </h4>
            <div className="space-y-4">
              {sortedCommunities.map((comm, idx) => (
                <Card key={idx}>
                  <CardHeader className="p-3 pb-0">
                    <CardTitle className="text-sm">Nível {comm.level}</CardTitle>
                    <CardDescription className="text-xs">ID: {comm.community_id}</CardDescription>
                  </CardHeader>
                  <CardContent className="p-3 pt-2">
                    <p className="text-xs text-muted-foreground line-clamp-4 hover:line-clamp-none transition-all">
                      {comm.summary || "Sem resumo disponível."}
                    </p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

import React from "react";
import { MetaData } from "../types/graph";
import { Card, CardContent } from "./ui/card";
import { colorFor } from "@/lib/colors";

interface LegendProps {
  meta: MetaData | null;
  colorMode: "type" | "community";
}

export const Legend: React.FC<LegendProps> = ({ meta, colorMode }) => {
  if (!meta || colorMode !== "type") return null;

  return (
    <Card className="absolute bottom-4 left-4 z-10 shadow-lg bg-background/95 backdrop-blur max-h-60 overflow-y-auto">
      <CardContent className="p-3">
        <h4 className="text-xs font-semibold uppercase text-muted-foreground mb-2">Tipos de Entidade</h4>
        <div className="flex flex-col gap-1.5">
          {meta.entity_types.map((type) => (
            <div key={type} className="flex items-center gap-2">
              <div 
                className="w-3 h-3 rounded-full shadow-sm" 
                style={{ backgroundColor: colorFor(type) }} 
              />
              <span className="text-xs">{type}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};

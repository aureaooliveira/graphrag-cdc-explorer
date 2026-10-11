import React, { createContext, useContext, useState } from "react";
import { useGraphData } from "../hooks/useGraphData";
import type { GraphHighlight } from "../types/graph";

type GraphDataValue = ReturnType<typeof useGraphData> & {
  highlight: GraphHighlight | null;
  setHighlight: (h: GraphHighlight | null) => void;
};

const GraphDataContext = createContext<GraphDataValue | null>(null);

/** Carrega o grafo uma única vez e o compartilha entre as telas (Grafo e
 *  Consultas), junto com o destaque ativo. */
export const GraphDataProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const data = useGraphData();
  const [highlight, setHighlight] = useState<GraphHighlight | null>(null);
  return (
    <GraphDataContext.Provider value={{ ...data, highlight, setHighlight }}>{children}</GraphDataContext.Provider>
  );
};

export function useGraph(): GraphDataValue {
  const ctx = useContext(GraphDataContext);
  if (!ctx) throw new Error("useGraph deve ser usado dentro de GraphDataProvider");
  return ctx;
}

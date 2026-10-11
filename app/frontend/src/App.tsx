import { useEffect, useState } from "react";
import { Network, MessageSquareText, History } from "lucide-react";
import { GraphPage } from "./pages/GraphPage";
import { QueryPage } from "./pages/QueryPage";
import { HistoryPage } from "./pages/HistoryPage";
import { api } from "./lib/api";
import { GraphDataProvider } from "./context/GraphDataContext";
import type { IndexInfo } from "./types/query";
import { cn } from "@/lib/utils";

type Tab = "graph" | "query" | "history";

const TABS: { id: Tab; label: string; icon: typeof Network }[] = [
  { id: "graph", label: "Grafo", icon: Network },
  { id: "query", label: "Consultas", icon: MessageSquareText },
  { id: "history", label: "Histórico", icon: History },
];

function App() {
  const [tab, setTab] = useState<Tab>(() => (localStorage.getItem("tab") as Tab) || "graph");
  const [index, setIndex] = useState<IndexInfo | null>(null);

  useEffect(() => {
    localStorage.setItem("tab", tab);
  }, [tab]);

  useEffect(() => {
    api.index().then(setIndex).catch(() => setIndex(null));
  }, []);

  const iv = index?.index_version;

  return (
    <GraphDataProvider>
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-background text-foreground">
      <header className="flex h-14 shrink-0 items-center gap-4 border-b px-4">
        <div className="font-semibold">GraphRAG · CDC</div>
        <nav className="flex gap-1">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm",
                tab === id ? "bg-primary text-primary-foreground" : "hover:bg-accent",
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ))}
        </nav>
        <div className="flex-1" />
        {index && (
          <div className="text-right text-xs text-muted-foreground" title={iv?.fingerprint}>
            {iv ? (
              <>
                Índice #{iv.id}
                {iv.label ? ` (${iv.label})` : ""} · GraphRAG {iv.graphrag_version}
                {iv.indexed_at ? ` · indexado em ${new Date(iv.indexed_at + (iv.indexed_at.includes("+") ? "" : "Z")).toLocaleDateString("pt-BR")}` : ""}
              </>
            ) : (
              "Índice não registrado"
            )}
            {!index.query_ready && <div className="text-destructive">Consultas indisponíveis: {index.query_error}</div>}
          </div>
        )}
      </header>
      <main className="min-h-0 flex-1">
        {/* As telas ficam montadas (só escondidas) para não perder o estado,
            por exemplo uma consulta em andamento ao abrir o grafo. */}
        <div className={cn("h-full", tab !== "graph" && "hidden")}>
          <GraphPage active={tab === "graph"} />
        </div>
        <div className={cn("h-full", tab !== "query" && "hidden")}>
          <QueryPage onOpenGraph={() => setTab("graph")} />
        </div>
        <div className={cn("h-full", tab !== "history" && "hidden")}>
          <HistoryPage onOpenGraph={() => setTab("graph")} active={tab === "history"} />
        </div>
      </main>
    </div>
    </GraphDataProvider>
  );
}

export default App;

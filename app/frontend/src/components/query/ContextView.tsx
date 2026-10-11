import React, { useState } from "react";
import { cn } from "@/lib/utils";
import { DataTable } from "./DataTable";

const LABELS: Record<string, string> = {
  entities: "Entidades",
  relationships: "Relações",
  reports: "Relatórios de comunidade",
  sources: "Trechos do texto",
  claims: "Afirmações",
};

interface ContextViewProps {
  records: Record<string, Record<string, unknown>[]>;
  contextText?: string;
}

/** Abas com as tabelas de contexto recuperadas e o texto exato inserido no prompt. */
export const ContextView: React.FC<ContextViewProps> = ({ records, contextText }) => {
  const tabs = Object.entries(records || {}).filter(([, rows]) => Array.isArray(rows) && rows.length > 0);
  const all = contextText ? [...tabs.map(([k]) => k), "__text"] : tabs.map(([k]) => k);
  const [active, setActive] = useState<string>(all[0] ?? "");
  if (!all.length) return <p className="text-xs text-muted-foreground">Nenhum contexto recuperado.</p>;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1">
        {tabs.map(([key, rows]) => (
          <button
            key={key}
            onClick={() => setActive(key)}
            className={cn(
              "rounded-md border px-2 py-1 text-xs",
              active === key ? "bg-primary text-primary-foreground" : "bg-muted hover:bg-accent",
            )}
          >
            {LABELS[key] ?? key} ({rows.length})
          </button>
        ))}
        {contextText && (
          <button
            onClick={() => setActive("__text")}
            className={cn(
              "rounded-md border px-2 py-1 text-xs",
              active === "__text" ? "bg-primary text-primary-foreground" : "bg-muted hover:bg-accent",
            )}
          >
            Texto enviado ao modelo
          </button>
        )}
      </div>
      {active === "__text" ? (
        <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap rounded border bg-muted/40 p-3 text-xs">{contextText}</pre>
      ) : (
        <DataTable rows={records[active] ?? []} />
      )}
    </div>
  );
};

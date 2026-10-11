import React, { useState } from "react";

const PREVIEW = 180;

function cellText(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

/** Tabela genérica para os registros de contexto do GraphRAG.
 *  Clique em uma linha para ver o texto completo das células. */
export const DataTable: React.FC<{ rows: Record<string, unknown>[]; maxColumns?: number }> = ({ rows, maxColumns = 7 }) => {
  const [expanded, setExpanded] = useState<number | null>(null);
  if (!rows?.length) return <p className="text-xs text-muted-foreground">Nenhum registro.</p>;
  const columns = Object.keys(rows[0]).slice(0, maxColumns);
  return (
    <div className="max-h-[420px] overflow-auto rounded border">
      <table className="w-full border-collapse text-xs">
        <thead className="sticky top-0 bg-muted">
          <tr>
            {columns.map((c) => (
              <th key={c} className="whitespace-nowrap border-b px-2 py-1.5 text-left font-semibold">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              className="cursor-pointer align-top odd:bg-background even:bg-muted/30 hover:bg-accent"
              onClick={() => setExpanded(expanded === i ? null : i)}
            >
              {columns.map((c) => {
                const text = cellText(row[c]);
                const full = expanded === i || text.length <= PREVIEW;
                return (
                  <td key={c} className="border-b px-2 py-1.5 whitespace-pre-wrap break-words">
                    {full ? text : text.slice(0, PREVIEW) + "…"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

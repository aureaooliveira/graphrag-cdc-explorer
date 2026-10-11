import React, { useMemo, useState } from "react";

interface MapBatch {
  batch: number;
  points: { answer?: string; description?: string; score?: number }[] | string;
  llm_calls?: number;
  prompt_tokens?: number;
  output_tokens?: number;
}

/** Etapa map da busca global: pontos-chave de cada lote, ordenados pela nota. */
export const MapView: React.FC<{ batches: MapBatch[]; contexts?: string[] }> = ({ batches, contexts }) => {
  const [showBatch, setShowBatch] = useState<number | null>(null);
  const points = useMemo(() => {
    const out: { batch: number; text: string; score: number }[] = [];
    for (const b of batches) {
      if (!Array.isArray(b.points)) continue;
      for (const p of b.points) out.push({ batch: b.batch, text: p.answer ?? p.description ?? "", score: p.score ?? 0 });
    }
    return out.sort((a, b) => b.score - a.score);
  }, [batches]);
  const relevant = points.filter((p) => p.score > 0);

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        {batches.length} lote(s) de relatórios de comunidade · {relevant.length} ponto(s)-chave com nota &gt; 0 (os de nota
        0 são descartados antes da síntese). Clique em um ponto para ver o lote de relatórios que o originou.
      </p>
      <div className="max-h-[420px] space-y-1.5 overflow-auto">
        {points.map((p, i) => (
          <div key={i}>
            <button
              className="flex w-full gap-2 rounded border px-2 py-1.5 text-left text-xs hover:bg-accent"
              onClick={() => setShowBatch(showBatch === i ? null : i)}
            >
              <span
                className={`shrink-0 rounded px-1.5 font-mono ${p.score > 0 ? "bg-emerald-100 text-emerald-800" : "bg-muted text-muted-foreground"}`}
              >
                {p.score}
              </span>
              <span className="shrink-0 text-muted-foreground">lote {p.batch + 1}</span>
              <span className="whitespace-pre-wrap">{p.text}</span>
            </button>
            {showBatch === i && contexts?.[p.batch] && (
              <pre className="mt-1 max-h-60 overflow-auto whitespace-pre-wrap rounded border bg-muted/40 p-2 text-[11px]">
                {contexts[p.batch]}
              </pre>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

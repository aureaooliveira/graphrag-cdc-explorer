import React, { useCallback, useEffect, useState } from "react";
import { ArrowLeft, RefreshCw, Trash2 } from "lucide-react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { RunView } from "../components/query/RunView";
import { api } from "../lib/api";
import { METHOD_INFO, type QueryRunDetail, type QueryRunSummary } from "../types/query";

const fmtDate = (s: string | null) => (s ? new Date(s.endsWith("Z") || s.includes("+") ? s : s + "Z").toLocaleString("pt-BR") : "");
const fmt = (n?: number | null) => (n ?? 0).toLocaleString("pt-BR");

export const HistoryPage: React.FC<{ onOpenGraph?: () => void; active?: boolean }> = ({ onOpenGraph, active = true }) => {
  const [items, setItems] = useState<QueryRunSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [method, setMethod] = useState("");
  const [source, setSource] = useState("");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<QueryRunDetail | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await api.runs({ method, source, q, limit: 200 });
      setItems(r.items);
      setTotal(r.total);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [method, source, q]);

  // Recarrega ao entrar na aba (novas consultas podem ter sido feitas).
  useEffect(() => {
    if (active) load();
  }, [load, active]);

  const open = async (id: string) => setSelected(await api.run(id));
  const remove = async (id: string) => {
    if (!confirm("Excluir esta consulta do histórico?")) return;
    await api.deleteRun(id);
    setSelected(null);
    load();
  };

  if (selected) {
    return (
      <div className="mx-auto h-full max-w-5xl overflow-y-auto p-4 pb-10">
        <div className="mb-4 flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => setSelected(null)}>
            <ArrowLeft className="mr-1 h-4 w-4" /> Voltar
          </Button>
          <div className="flex-1" />
          <Button variant="outline" size="sm" onClick={() => remove(selected.id)}>
            <Trash2 className="mr-1 h-4 w-4" /> Excluir
          </Button>
        </div>
        <div className="mb-4 space-y-1">
          <div className="flex flex-wrap gap-2">
            <Badge>{METHOD_INFO[selected.method]?.label ?? selected.method}</Badge>
            <Badge variant="outline">nível {selected.params?.community_level}</Badge>
            <Badge variant="outline">{selected.params?.response_type}</Badge>
            <Badge variant="outline">{selected.source}</Badge>
            {selected.index_version_id && <Badge variant="outline">índice #{selected.index_version_id}</Badge>}
          </div>
          <h2 className="text-lg font-semibold">{selected.question}</h2>
          <p className="text-xs text-muted-foreground">
            {fmtDate(selected.created_at)} · id {selected.id}
          </p>
        </div>
        <RunView
          method={selected.method}
          steps={selected.steps}
          answer={selected.response ?? ""}
          running={selected.status === "running"}
          error={selected.error}
          onOpenGraph={onOpenGraph}
        />
      </div>
    );
  }

  return (
    <div className="mx-auto flex h-full max-w-7xl flex-col gap-3 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <input
          className="h-9 w-72 rounded-md border border-input bg-transparent px-3 text-sm"
          placeholder="Buscar na pergunta..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select className="h-9 rounded-md border border-input bg-transparent px-2 text-sm" value={method} onChange={(e) => setMethod(e.target.value)}>
          <option value="">Todas as modalidades</option>
          {Object.entries(METHOD_INFO).map(([k, v]) => (
            <option key={k} value={k}>
              {v.label}
            </option>
          ))}
        </select>
        <select className="h-9 rounded-md border border-input bg-transparent px-2 text-sm" value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="">Todas as origens</option>
          <option value="ui">Interface</option>
          <option value="evaluation">Avaliação</option>
          <option value="api">API</option>
        </select>
        <Button variant="outline" size="sm" onClick={load}>
          <RefreshCw className={`mr-1 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Atualizar
        </Button>
        <span className="text-xs text-muted-foreground">{total} consulta(s)</span>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="flex-1 overflow-auto rounded border">
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-0 bg-muted text-left text-xs">
            <tr>
              <th className="px-3 py-2">Data</th>
              <th className="px-3 py-2">Modalidade</th>
              <th className="px-3 py-2">Pergunta</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2 text-right">Chamadas</th>
              <th className="px-3 py-2 text-right">Tokens (entrada / saída)</th>
              <th className="px-3 py-2 text-right">Tempo</th>
            </tr>
          </thead>
          <tbody>
            {items.map((r) => (
              <tr key={r.id} className="cursor-pointer border-b hover:bg-accent" onClick={() => open(r.id)}>
                <td className="whitespace-nowrap px-3 py-2 text-xs">{fmtDate(r.created_at)}</td>
                <td className="px-3 py-2">
                  <Badge variant="outline">{METHOD_INFO[r.method]?.label ?? r.method}</Badge>
                </td>
                <td className="max-w-md truncate px-3 py-2">{r.question}</td>
                <td className="px-3 py-2 text-xs">
                  <span className={r.status === "error" ? "text-destructive" : r.status === "running" ? "text-amber-600" : "text-emerald-700"}>
                    {r.status === "completed" ? "concluída" : r.status === "error" ? "erro" : "em andamento"}
                  </span>
                </td>
                <td className="px-3 py-2 text-right text-xs">{fmt(r.llm_calls)}</td>
                <td className="whitespace-nowrap px-3 py-2 text-right text-xs">
                  {fmt(r.prompt_tokens)} / {fmt(r.output_tokens)}
                </td>
                <td className="px-3 py-2 text-right text-xs">{r.completion_time ? `${r.completion_time.toFixed(1)} s` : ""}</td>
              </tr>
            ))}
            {!items.length && !loading && (
              <tr>
                <td colSpan={7} className="px-3 py-8 text-center text-sm text-muted-foreground">
                  Nenhuma consulta registrada.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

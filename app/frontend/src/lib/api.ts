import type { IndexInfo, QueryRequest, QueryRunDetail, QueryRunSummary } from "../types/query";

/**
 * Base da API. Vazio = mesma origem: em desenvolvimento o Vite repassa /api
 * para o backend (ver vite.config.ts). Defina VITE_API_URL para acessar a API
 * diretamente (ex.: http://localhost:8000).
 */
export const API_URL: string = import.meta.env.VITE_API_URL ?? "";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* corpo não é JSON */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  index: () => fetch(`${API_URL}/api/index`).then((r) => json<IndexInfo>(r)),
  reloadIndex: () => fetch(`${API_URL}/api/index/reload`, { method: "POST" }).then((r) => json<IndexInfo>(r)),
  runs: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => v !== undefined && v !== "" && qs.set(k, String(v)));
    return fetch(`${API_URL}/api/runs?${qs}`).then((r) => json<{ total: number; items: QueryRunSummary[] }>(r));
  },
  run: (id: string) => fetch(`${API_URL}/api/runs/${id}`).then((r) => json<QueryRunDetail>(r)),
  deleteRun: (id: string) =>
    fetch(`${API_URL}/api/runs/${id}`, { method: "DELETE" }).then((r) => {
      if (!r.ok) throw new Error(`${r.status}`);
    }),
};

/**
 * Executa uma consulta e entrega cada evento SSE conforme chega.
 * (EventSource não aceita POST, então o fluxo é lido manualmente.)
 */
export async function streamQuery(
  req: QueryRequest,
  onEvent: (type: string, payload: any) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_URL}/api/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
    signal,
  });
  if (!res.ok || !res.body) {
    await json(res); // lança o erro com o detalhe do backend
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      let type = "message";
      const data: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) type = line.slice(6).trim();
        else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
      }
      if (data.length) onEvent(type, JSON.parse(data.join("\n")));
    }
  }
}

import type { GraphData, GraphHighlight } from "../types/graph";
import type { QueryMethod, QueryStep } from "../types/query";

const norm = (s: unknown) => String(s ?? "").trim().toUpperCase();
const linkKey = (a: string, b: string) => `${a}|${b}`;

/** Ids citados no formato do GraphRAG, ex.: "[Data: Reports (12, 30, +more)]". */
function citedIds(text: string, kind: "Reports" | "Sources" | "Entities"): Set<string> {
  const ids = new Set<string>();
  const re = new RegExp(`${kind}\\s*\\(([^)]*)\\)`, "g");
  for (const m of text.matchAll(re)) {
    for (const part of m[1].split(",")) {
      const id = part.trim();
      if (/^\d+$/.test(id)) ids.add(id);
    }
  }
  return ids;
}

export interface ContextHighlight extends GraphHighlight {
  /** como o destaque foi calculado, em uma frase */
  basis: string;
  missing: number;
  /** número de relações do grafo entre os nós destacados que estão no destaque */
  linkCount: number;
}

/**
 * Calcula quais nós e relações do grafo correspondem ao contexto de uma consulta.
 *
 * - local / drift: entidades e relações do contexto (as tabelas usam o título da
 *   entidade, que é o rótulo do nó no grafo);
 * - basic: entidades extraídas dos trechos recuperados pela busca vetorial (a busca
 *   basic não usa o grafo; o destaque mostra o que o grafo sabe sobre esses trechos);
 * - global: entidades das comunidades cujos relatórios foram citados nos pontos-chave
 *   relevantes (nota > 0) e na resposta final.
 */
export function computeContextHighlight(
  method: QueryMethod,
  steps: QueryStep[],
  answer: string,
  graph: GraphData,
): ContextHighlight | null {
  const byLabel = new Map(graph.nodes.map((n) => [norm(n.label), n.id]));
  const nodeIds = new Set<string>();
  const linkKeys = new Set<string>();
  let missing = 0;
  let basis = "";

  const context = steps.find((s) => s.type === "context")?.payload;
  const records: Record<string, any[]> = context?.records ?? {};

  if (method === "local" || method === "drift") {
    for (const e of records.entities ?? []) {
      const id = byLabel.get(norm(e.entity ?? e.title));
      if (id) nodeIds.add(id);
      else missing++;
    }
    const fromEntities = nodeIds.size;
    for (const r of records.relationships ?? []) {
      const a = byLabel.get(norm(r.source));
      const b = byLabel.get(norm(r.target));
      if (a && b) {
        nodeIds.add(a);
        nodeIds.add(b);
        linkKeys.add(linkKey(a, b));
        linkKeys.add(linkKey(b, a));
      }
    }
    const extra = nodeIds.size - fromEntities;
    basis =
      `Entidades (${fromEntities}) e relações incluídas no contexto enviado ao modelo` +
      (extra > 0 ? `, mais ${extra} entidade(s) que só aparecem como extremidade dessas relações.` : ".");
  } else if (method === "basic") {
    const sourceIds = new Set((records.sources ?? []).map((s) => String(s.id)));
    for (const n of graph.nodes) {
      if (n.text_units?.some((t) => sourceIds.has(t))) nodeIds.add(n.id);
    }
    basis = `Entidades extraídas dos ${sourceIds.size} trechos recuperados pela busca vetorial (a busca basic não usa o grafo).`;
  } else {
    const mapEnd: any[] = steps.find((s) => s.type === "map_end")?.payload ?? [];
    const text = [
      ...mapEnd.flatMap((b) => (Array.isArray(b.points) ? b.points : []))
        .filter((p: any) => (p.score ?? 0) > 0)
        .map((p: any) => p.answer ?? p.description ?? ""),
      answer,
    ].join("\n");
    const communities = citedIds(text, "Reports");
    for (const n of graph.nodes) {
      if (n.communities?.some((c) => communities.has(String(c.community_id)))) nodeIds.add(n.id);
    }
    basis = `Entidades das ${communities.size} comunidades cujos relatórios foram citados nos pontos-chave relevantes e na resposta.`;
  }

  if (!nodeIds.size) return null;

  // Relações do grafo entre os nós destacados (para local/drift, além das do contexto).
  if (method !== "local" && method !== "drift") {
    for (const e of graph.edges) {
      if (nodeIds.has(e.source) && nodeIds.has(e.target)) {
        linkKeys.add(linkKey(e.source, e.target));
        linkKeys.add(linkKey(e.target, e.source));
      }
    }
  }

  const linkCount = graph.edges.filter(
    (e) => nodeIds.has(e.source) && nodeIds.has(e.target) && linkKeys.has(linkKey(e.source, e.target)),
  ).length;

  return {
    nodeIds,
    linkKeys,
    missing,
    basis,
    linkCount,
    title: "Contexto da consulta",
    description: `${nodeIds.size} entidade(s) e ${linkCount} relação(ões). ${basis}`,
  };
}

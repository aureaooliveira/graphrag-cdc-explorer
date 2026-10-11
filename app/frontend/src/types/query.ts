export type QueryMethod = "local" | "global" | "drift" | "basic";

export interface QueryRequest {
  question: string;
  method: QueryMethod;
  community_level?: number;
  response_type?: string;
  dynamic_community_selection?: boolean;
}

/** Etapa de uma consulta (evento SSE ou registro de query_steps). */
export interface QueryStep {
  type: string;
  payload: any;
  seq?: number;
  created_at?: string;
}

export interface QueryRunSummary {
  id: string;
  created_at: string | null;
  finished_at: string | null;
  question: string;
  method: QueryMethod;
  params: { community_level: number; response_type: string; dynamic_community_selection: boolean };
  source: string;
  status: "running" | "completed" | "error";
  index_version_id: number | null;
  evaluation_run_id: number | null;
  question_id: number | null;
  repetition: number | null;
  response: string | null;
  error: string | null;
  completion_time: number | null;
  llm_calls: number | null;
  prompt_tokens: number | null;
  output_tokens: number | null;
  usage_by_category: {
    llm_calls?: Record<string, number>;
    prompt_tokens?: Record<string, number>;
    output_tokens?: Record<string, number>;
  } | null;
}

export interface QueryRunDetail extends QueryRunSummary {
  steps: QueryStep[];
}

export interface IndexInfo {
  index_version: {
    id: number;
    fingerprint: string;
    label: string | null;
    indexed_at: string | null;
    graphrag_version: string | null;
    models: Record<string, string> | null;
    stats: Record<string, number> | null;
  } | null;
  query_ready: boolean;
  query_error: string | null;
}

export const METHOD_INFO: Record<QueryMethod, { label: string; description: string }> = {
  local: {
    label: "Local",
    description:
      "Parte das entidades mais próximas da pergunta e reúne suas relações, relatórios de comunidade e trechos originais. Indicada para perguntas pontuais.",
  },
  global: {
    label: "Global",
    description:
      "Map-reduce sobre os relatórios de comunidade: cada lote gera pontos-chave com nota (map) e eles são sintetizados (reduce). Indicada para perguntas amplas. É a mais cara.",
  },
  drift: {
    label: "DRIFT",
    description:
      "Gera uma resposta inicial a partir dos relatórios de comunidade e a aprofunda com perguntas de acompanhamento respondidas por busca local.",
  },
  basic: {
    label: "Basic (baseline)",
    description:
      "RAG vetorial tradicional: recupera os trechos de texto mais similares à pergunta, sem usar o grafo. É o baseline da avaliação.",
  },
};

// Cores do grafo, compartilhadas por GraphView, Legend e ContextGraph.
//
// Tipos de entidade: paleta fixa, com uma cor bem distinta para cada um dos 14 tipos
// da taxonomia. Comunidades: matiz espaçado pelo ângulo áureo a partir do id, para
// que comunidades com ids próximos (0, 1, 2...) tenham cores bem diferentes.
// (A versão anterior usava um hash do texto "comm-<id>"; textos que diferem só no
// último caractere geravam matizes quase iguais.)

const TYPE_COLORS: Record<string, string> = {
  CONSUMIDOR: "#1f77b4",
  FORNECEDOR: "#d62728",
  ORGAO_ENTIDADE: "#9467bd",
  PRODUTO: "#ff7f0e",
  SERVICO: "#e6b800",
  CONTRATO: "#8c564b",
  DIREITO: "#2ca02c",
  OBRIGACAO: "#e377c2",
  PRATICA_ABUSIVA: "#bcbd22",
  INSTITUTO_JURIDICO: "#17becf",
  SANCAO_ADMINISTRATIVA: "#393b79",
  INFRACAO_PENAL: "#843c39",
  INSTRUMENTO_PROCESSUAL: "#637939",
  DISPOSITIVO_LEGAL: "#9e9e9e",
};

const cache: Record<string, string> = {};

function hashColor(seed: string): string {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) hash = seed.charCodeAt(i) + ((hash << 5) - hash);
  return `hsl(${Math.abs(hash) % 360}, 70%, 55%)`;
}

/** Cor de um tipo de entidade (paleta fixa; hash como reserva para tipos desconhecidos). */
export function colorFor(type: string): string {
  const key = (type || "unknown").toUpperCase();
  if (TYPE_COLORS[key]) return TYPE_COLORS[key];
  if (!cache[key]) cache[key] = hashColor(key);
  return cache[key];
}

/** Cor de uma comunidade: matiz pelo ângulo áureo (~137,5°), alternando a luminosidade. */
export function communityColor(id: number | string): string {
  const n = Number(id);
  if (!Number.isFinite(n)) return hashColor(String(id));
  const hue = (n * 137.508) % 360;
  const light = n % 3 === 0 ? 45 : n % 3 === 1 ? 58 : 70;
  return `hsl(${hue.toFixed(1)}, 70%, ${light}%)`;
}

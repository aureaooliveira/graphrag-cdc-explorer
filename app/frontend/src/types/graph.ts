export interface CommunityLevel {
  level: number;
  community_id: string;
  summary: string;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  description: string;
  degree: number;
  communities: CommunityLevel[];
  /** ids curtos dos trechos (text units) de onde a entidade foi extraída */
  text_units?: string[];
}

export interface GraphEdge {
  source: string;
  target: string;
  description: string;
  weight: number;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface CommunityInfo {
  id: string;
  level: number;
  title: string;
  summary: string;
  full_content: string;
  entity_count: number;
}

export interface MetaData {
  total_nodes: number;
  total_edges: number;
  entity_types: string[];
  community_levels: number[];
}

/** Destaque de parte do grafo (ex.: o contexto usado por uma consulta). */
export interface GraphHighlight {
  /** ids dos nós destacados */
  nodeIds: Set<string>;
  /** pares "idOrigem|idDestino" (nos dois sentidos) das relações destacadas */
  linkKeys: Set<string>;
  /** de onde veio o destaque, para exibir no banner */
  title: string;
  description: string;
}

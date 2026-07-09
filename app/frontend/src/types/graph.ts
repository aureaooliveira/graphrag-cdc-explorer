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

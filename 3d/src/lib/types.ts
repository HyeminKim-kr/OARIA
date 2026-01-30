export interface NodeMetadata {
  pmid?: string;
  journal?: string;
  pubdate?: string;
  abstract?: string;
  paper_count?: number;
  certainty_score?: number;
  domain?: string;
}

export interface GraphNode {
  id: string;
  type: "paper" | "author" | "keyword" | "concept";
  label: string;
  cluster?: string;
  metadata?: NodeMetadata;
  x?: number;
  y?: number;
  z?: number;
}

export interface GraphLink {
  source: string;
  target: string;
  type: "similar" | "authored" | "contains" | "causal" | "correlational" | "hierarchical" | "contradictory";
  similarity?: number;
  weight?: number;
  evidence_hint?: string;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

export interface VectorGraphResponse {
  nodes: GraphNode[];
  links: GraphLink[];
  query: string;
  total_papers: number;
  total_authors: number;
  total_keywords: number;
}

export interface VectorSearchRequest {
  query: string;
  limit?: number;
  min_similarity?: number;
  include_authors?: boolean;
  include_keywords?: boolean;
}

export interface ActiveFilters {
  paper: boolean;
  author: boolean;
  keyword: boolean;
  concept: boolean;
}

export const NODE_COLORS: Record<string, string> = {
  paper: "#3498db",
  author: "#2ecc71",
  keyword: "#f39c12",
  concept: "#9b59b6",
};

export const LINK_COLORS: Record<string, string> = {
  similar: "#7f8c8d",
  authored: "#27ae60",
  contains: "#e67e22",
  causal: "#e74c3c",
  correlational: "#3498db",
  hierarchical: "#9b59b6",
  contradictory: "#c0392b",
};

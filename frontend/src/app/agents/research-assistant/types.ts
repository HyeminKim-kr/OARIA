// ─────────────────────────────────────────────────────────────
// Research Assistant - Types
// Vector-Based 3D Reasoning Engine
// ─────────────────────────────────────────────────────────────

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
  // 3D 위치 (force graph가 설정)
  x?: number;
  y?: number;
  z?: number;
}

export interface GraphLink {
  source: string | GraphNode;
  target: string | GraphNode;
  type: "similar" | "authored" | "contains" | "causal" | "correlational" | "hierarchical" | "contradictory";
  similarity?: number;
  weight?: number;
  evidence_hint?: string;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

export interface ClusterConfig {
  color: string;
  label: string;
}

export interface ReasoningStep {
  id: string;
  step_number: number;
  selected_node: string;
  connection_reason: string;
  next_move_reason: string;
  confidence: number;
}

export interface ReasoningResult {
  conclusion: string;
  supporting_nodes: string[];
  confidence_score: number;
  failure_modes: string[];
  next_suggestions: string[];
}

export interface SemanticDecomposition {
  core_question: string;
  concept_nodes: Array<{
    node_id: string;
    label: string;
    semantic_embedding: string;
    domain: string;
    certainty_score: number;
  }>;
  relation_edges: Array<{
    source: string;
    target: string;
    edge_type: string;
    weight: number;
    evidence_hint: string;
  }>;
}

export type ViewMode = "landing" | "graph";

export interface ActiveFilters {
  paper: boolean;
  author: boolean;
  keyword: boolean;
  concept: boolean;
}

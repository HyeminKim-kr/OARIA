export type NodeType = 'PAPER' | 'CONCEPT' | 'METHOD' | 'AUTHOR';
export type EdgeType = 'CITES' | 'RELATED_TO' | 'AUTHORED_BY' | 'SIMILARITY';

export interface BaseEntity {
    id: string;
    created_at?: string;
}

export interface MapNode extends BaseEntity {
    label: string;
    type: NodeType;
    description?: string;

    // Visuals - Precomputed layout coordinates
    x: number;
    y: number;
    z?: number;
    size?: number;
    color?: string;

    // Metadata
    cluster_id?: string;
    year?: number;
    citation_count?: number;

    // Exploration State
    score?: number;
}

export interface MapEdge extends BaseEntity {
    source: string;
    target: string;
    type: EdgeType;
    weight: number;
}

export interface GraphData {
    nodes: MapNode[];
    edges: MapEdge[];
}

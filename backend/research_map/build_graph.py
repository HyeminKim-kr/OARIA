import json
import os
import logging
from typing import List, Dict
import numpy as np
from embedding import PaperEmbedder

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DATA_FILE = os.path.join(os.path.dirname(__file__), 'ingested_data.json')
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), 'graph_data.json')

class GraphBuilder:
    def __init__(self):
        self.embedder = PaperEmbedder(mock=True)

    def load_data(self) -> List[Dict]:
        if not os.path.exists(DATA_FILE):
            logging.error(f"Data file not found: {DATA_FILE}")
            return []
        with open(DATA_FILE, 'r') as f:
            return json.load(f)

    def compute_similarity(self, vectors: List[List[float]]) -> np.ndarray:
        """
        Computes cosine similarity matrix.
        Returns N x N matrix.
        """
        # Normalize vectors
        vecs = np.array(vectors)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        # Avoid division by zero
        norms[norms == 0] = 1.0
        normalized = vecs / norms
        
        # Dot product
        return np.dot(normalized, normalized.T)

    def build_graph(self, k: int = 5):
        papers = self.load_data()
        if not papers:
            return

        logging.info(f"Loaded {len(papers)} papers. Generating Embeddings...")
        
        # 1. Embed Abstracts
        # Combine title and abstract for better context
        texts = [f"{p.get('title', '')} {p.get('abstract', '')}" for p in papers]
        vectors = self.embedder.embed_batch(texts)
        
        # 2. Compute Similarity
        logging.info("Computing Similarity Matrix...")
        sim_matrix = self.compute_similarity(vectors)

        # 3. Create Edges
        nodes = []
        edges = []
        
        # Create Nodes
        for i, p in enumerate(papers):
            nodes.append({
                "id": p['id'],
                "label": p['title'],
                "year": p['year'],
                "citation_count": p['citations'],
                "type": "PAPER",
                # Random layout for now (simulating UMAP)
                "x": np.random.uniform(-1000, 1000),
                "y": np.random.uniform(-1000, 1000)
            })

        # Create Edges (k-NN)
        logging.info(f"Generating Top-{k} Edges...")
        for i in range(len(papers)):
            # Get top K similar indices (excluding self)
            # argsort returns indices that sort the array, flip to get descending
            sorted_indices = np.argsort(sim_matrix[i])[::-1]
            
            count = 0
            for idx in sorted_indices:
                if idx == i: continue
                if count >= k: break
                
                score = float(sim_matrix[i][idx])
                if score < 0.1: continue # Threshold

                edges.append({
                    "source": papers[i]['id'],
                    "target": papers[idx]['id'],
                    "type": "SIMILARITY",
                    "weight": score
                })
                count += 1

        # 4. Save
        graph_data = {
            "nodes": nodes,
            "edges": edges
        }
        
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(graph_data, f, indent=2)
        
        logging.info(f"Graph built successfully! Saved {len(nodes)} nodes and {len(edges)} edges to {OUTPUT_FILE}")

if __name__ == "__main__":
    builder = GraphBuilder()
    builder.build_graph()

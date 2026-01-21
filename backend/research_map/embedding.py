import logging
import random
from typing import List
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class PaperEmbedder:
    """
    Service to generate vector embeddings for paper abstracts.
    """
    def __init__(self, model_name: str = "specter2", mock: bool = True):
        self.mock = mock
        self.model_name = model_name
        self.dimension = 768
        
        if not self.mock:
            logging.info(f"Loading Real Model: {model_name}...")
            # from sentence_transformers import SentenceTransformer
            # self.model = SentenceTransformer('allenai/specter2')
            pass
        else:
            logging.warning("Running in MOCK mode. Vectors are random noise.")

    def embed(self, text: str) -> List[float]:
        """
        Embeds a single string.
        """
        if self.mock:
            # Return random unit vector
            vec = np.random.rand(self.dimension).astype(np.float32)
            vec /= np.linalg.norm(vec)
            return vec.tolist()
        
        # Real implementation
        # return self.model.encode(text).tolist()
        return []

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embeds a batch of strings.
        """
        return [self.embed(t) for t in texts]

# Simple CLI test
if __name__ == "__main__":
    embedder = PaperEmbedder(mock=True)
    text = "Attention mechanisms have revolutionized natural language processing..."
    vector = embedder.embed(text)
    
    logging.info(f"Generated Vector for text length {len(text)}")
    logging.info(f"Vector dim: {len(vector)}")
    logging.info(f"First 5 values: {vector[:5]}")

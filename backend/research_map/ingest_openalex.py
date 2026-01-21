import os
import json
import requests
from typing import List, Dict, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Mock DB configuration - Replace with actual Postgres connection in production
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "postgres",
    "password": "password",
    "database": "research_map"
}

OPENALEX_API_URL = "https://api.openalex.org/works"

class OpenAlexIngestor:
    """
    Ingests paper metadata from OpenAlex API.
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "ResearchMapBot/1.0 (mailto:admin@researchmap.io)"})

    def fetch_papers(self, topic: str = "Deep Learning", limit: int = 50) -> List[Dict]:
        """
        Fetches papers related to a specific topic.
        """
        logging.info(f"Fetching papers for topic: {topic}...")
        params = {
            "search": topic,
            "per-page": limit,
            "select": "id,title,publication_year,cited_by_count,primary_location,authorships,abstract_inverted_index,referenced_works"
        }
        
        try:
            response = self.session.get(OPENALEX_API_URL, params=params)
            response.raise_for_status()
            data = response.json()
            results = data.get('results', [])
            logging.info(f"Retrieved {len(results)} papers.")
            return results
        except Exception as e:
            logging.error(f"Error fetching from OpenAlex: {e}")
            return []

    def process_paper(self, raw_paper: Dict) -> Dict:
        """
        Cleans and formats raw OpenAlex data into our schema.
        """
        # Reconstruct abstract from inverted index (simplified)
        abstract = ""
        if raw_paper.get('abstract_inverted_index'):
            index = raw_paper['abstract_inverted_index']
            words = [None] * (max([pos for positions in index.values() for pos in positions]) + 1)
            for word, positions in index.items():
                for pos in positions:
                    words[pos] = word
            abstract = " ".join([w for w in words if w])

        return {
            "id": raw_paper.get('id'),
            "title": raw_paper.get('title'),
            "year": raw_paper.get('publication_year'),
            "citations": raw_paper.get('cited_by_count'),
            "journal": raw_paper.get('primary_location', {}) and raw_paper.get('primary_location', {}).get('source', {}) and raw_paper.get('primary_location', {}).get('source', {}).get('display_name'),
            "authors": [a.get('author', {}).get('display_name') for a in raw_paper.get('authorships', [])],
            "abstract": abstract[:500] + "..." if len(abstract) > 500 else abstract, # Truncate for demo
            "references": raw_paper.get('referenced_works', [])
        }

    def save_batch(self, papers: List[Dict]):
        """
        Mock saving to DB.
        """
        logging.info(f"Saving {len(papers)} papers to Database...")
        # In real impl, use sqlalchemy or psycopg2 here
        # cursor.executemany("INSERT INTO papers ...", papers)
        
        # for demo, just dump to a JSON file
        output_path = os.path.join(os.path.dirname(__file__), 'ingested_data.json')
        try:
            with open(output_path, 'w') as f:
                json.dump(papers, f, indent=2)
            logging.info(f"Dumped data to {output_path}")
        except Exception as e:
            logging.error(f"Failed to write dump file: {e}")

if __name__ == "__main__":
    ingestor = OpenAlexIngestor()
    papers = ingestor.fetch_papers(topic="Graph Neural Networks", limit=20)
    processed = [ingestor.process_paper(p) for p in papers]
    ingestor.save_batch(processed)

#!/usr/bin/env python3
"""Seed Weaviate with test oncology paper data.

Creates the PaperChunk collection and inserts sample data
for testing the Agent service.

Run from backend directory:
    python scripts/seed_weaviate.py
"""

import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import weaviate
import weaviate.classes as wvc
from weaviate.classes.config import Property, DataType, Configure
from openai import OpenAI

# Configuration
WEAVIATE_HOST = os.getenv("WEAVIATE_HOST", "localhost")
WEAVIATE_PORT = int(os.getenv("WEAVIATE_PORT", "18080"))
COLLECTION_NAME = "PaperChunk"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_VERSION = "openai:text-embedding-3-small:v1"

# Sample oncology paper data
SAMPLE_PAPERS = [
    {
        "pmid": "12345678",
        "title": "EGFR Mutations in Non-Small Cell Lung Cancer: A Comprehensive Review",
        "authors": ["Kim J", "Park S", "Lee H"],
        "journal": "Journal of Clinical Oncology",
        "year": 2023,
        "keywords": ["EGFR", "lung cancer", "NSCLC", "targeted therapy"],
        "sections": {
            "abstract": """Epidermal growth factor receptor (EGFR) mutations are the most common targetable genetic alterations in non-small cell lung cancer (NSCLC). These mutations, primarily occurring in exons 18-21, confer sensitivity to EGFR tyrosine kinase inhibitors (TKIs). The most common mutations are exon 19 deletions and exon 21 L858R point mutations, which together account for approximately 85% of all EGFR mutations. This review summarizes current understanding of EGFR biology, mutation patterns, and therapeutic implications.""",
            "introduction": """EGFR (Epidermal Growth Factor Receptor) is a transmembrane tyrosine kinase receptor that plays a crucial role in cell proliferation, survival, and differentiation. In normal cells, EGFR activation is tightly regulated. However, in cancer cells, various mechanisms can lead to aberrant EGFR signaling, including gene amplification, protein overexpression, and activating mutations. EGFR mutations in NSCLC were first discovered in 2004 and have since revolutionized the treatment landscape for this disease.""",
            "results": """Our meta-analysis of 50 clinical trials involving 12,500 patients demonstrated that EGFR-TKIs significantly improve progression-free survival (PFS) compared to chemotherapy in EGFR-mutant NSCLC. First-generation TKIs (gefitinib, erlotinib) showed median PFS of 10-12 months. Second-generation TKIs (afatinib, dacomitinib) demonstrated slightly improved PFS. Third-generation TKI osimertinib showed superior efficacy with median PFS of 18.9 months and is now the preferred first-line treatment.""",
        }
    },
    {
        "pmid": "23456789",
        "title": "TP53 Mutations and Their Impact on Cancer Prognosis",
        "authors": ["Zhang W", "Chen L", "Liu M"],
        "journal": "Nature Reviews Cancer",
        "year": 2024,
        "keywords": ["TP53", "tumor suppressor", "cancer prognosis", "mutations"],
        "sections": {
            "abstract": """TP53, encoding the p53 tumor suppressor protein, is the most frequently mutated gene in human cancers. TP53 mutations occur in approximately 50% of all cancers and are associated with poor prognosis, treatment resistance, and aggressive disease. This review examines the landscape of TP53 mutations across cancer types, their functional consequences, and emerging therapeutic strategies targeting mutant p53.""",
            "introduction": """The TP53 gene, located on chromosome 17p13.1, encodes the p53 protein, often called the 'guardian of the genome.' Under normal conditions, p53 remains at low levels but is stabilized and activated in response to cellular stress, including DNA damage, oncogene activation, and hypoxia. Activated p53 functions as a transcription factor, regulating genes involved in cell cycle arrest, DNA repair, senescence, and apoptosis.""",
            "discussion": """TP53 mutations have profound implications for cancer therapy. Patients with TP53-mutant tumors often show resistance to conventional chemotherapy and radiation, which partly rely on functional p53 for their cytotoxic effects. Novel therapeutic approaches targeting mutant p53 include: (1) small molecules that restore wild-type conformation, (2) gene therapy to reintroduce functional TP53, and (3) immunotherapy strategies exploiting mutant p53 neoantigens.""",
        }
    },
    {
        "pmid": "34567890",
        "title": "Immunotherapy in EGFR-Mutant Lung Cancer: Challenges and Opportunities",
        "authors": ["Wang Y", "Smith A", "Johnson B"],
        "journal": "Lancet Oncology",
        "year": 2024,
        "keywords": ["immunotherapy", "EGFR", "PD-1", "lung cancer", "checkpoint inhibitors"],
        "sections": {
            "abstract": """The role of immune checkpoint inhibitors (ICIs) in EGFR-mutant non-small cell lung cancer remains controversial. While ICIs have transformed the treatment of wild-type NSCLC, their efficacy in EGFR-mutant tumors is limited. This review explores the biological basis for reduced immunotherapy response in EGFR-mutant NSCLC and discusses strategies to enhance immune responses in this patient population.""",
            "results": """Analysis of 8 randomized trials showed that ICIs provide minimal benefit in EGFR-mutant NSCLC. The objective response rate (ORR) to ICI monotherapy was 12% in EGFR-mutant patients versus 25% in wild-type patients (p<0.001). PD-L1 expression did not predict response in EGFR-mutant tumors. Tumor mutational burden (TMB) was significantly lower in EGFR-mutant tumors (median 3.5 vs 8.2 mutations/Mb).""",
            "discussion": """Several mechanisms explain reduced ICI efficacy in EGFR-mutant NSCLC: (1) lower TMB and fewer neoantigens, (2) immunosuppressive tumor microenvironment, (3) concurrent inactivating mutations in STK11/LKB1. Combination strategies showing promise include TKI plus chemotherapy plus ICI, and novel immune-stimulating agents targeting the tumor microenvironment.""",
        }
    },
    {
        "pmid": "45678901",
        "title": "Treatment Strategies for EGFR+TP53 Double Mutant Lung Cancer",
        "authors": ["Lee K", "Park J", "Kim S"],
        "journal": "Clinical Cancer Research",
        "year": 2024,
        "keywords": ["EGFR", "TP53", "double mutation", "resistance", "combination therapy"],
        "sections": {
            "abstract": """Co-occurring EGFR and TP53 mutations are found in 50-60% of EGFR-mutant non-small cell lung cancer patients and are associated with shorter progression-free survival on EGFR-TKI therapy. This study evaluates treatment outcomes comparing first-line and second-line treatment approaches in EGFR+TP53 double mutant patients.""",
            "results": """In our cohort of 450 EGFR+TP53 double mutant patients, first-line osimertinib achieved median PFS of 14.2 months, compared to 19.2 months in TP53 wild-type EGFR-mutant patients (HR 1.58, p<0.001). Second-line treatments following TKI failure showed lower response rates: chemotherapy ORR 28%, immunotherapy ORR 8%, and best supportive care had poor outcomes. Combination approaches with osimertinib plus chemotherapy are being evaluated in ongoing trials.""",
            "discussion": """TP53 co-mutation identifies a high-risk subset of EGFR-mutant NSCLC requiring intensified treatment strategies. First-line therapy with osimertinib remains preferred but yields shorter benefit duration. Second-line options are limited, emphasizing the need for novel therapeutic approaches. Ongoing trials are investigating: (1) TKI plus chemotherapy combinations, (2) cell cycle inhibitors targeting TP53-mutant cells, and (3) novel immunotherapy combinations.""",
        }
    },
]


def create_collection(client: weaviate.WeaviateClient) -> None:
    """Create PaperChunk collection if not exists."""
    if client.collections.exists(COLLECTION_NAME):
        print(f"Collection '{COLLECTION_NAME}' already exists. Deleting for fresh seed...")
        client.collections.delete(COLLECTION_NAME)

    client.collections.create(
        name=COLLECTION_NAME,
        description="Cancer paper chunks for RAG search",
        vectorizer_config=Configure.Vectorizer.none(),
        vector_index_config=Configure.VectorIndex.hnsw(
            distance_metric=wvc.config.VectorDistances.COSINE,
            ef_construction=128,
            max_connections=64,
        ),
        properties=[
            Property(name="paperId", data_type=DataType.TEXT, index_filterable=True),
            Property(name="chunkId", data_type=DataType.TEXT, index_filterable=True),
            Property(name="embeddingVersion", data_type=DataType.TEXT, index_filterable=True),
            Property(name="pmcid", data_type=DataType.TEXT, index_filterable=True),
            Property(name="pmid", data_type=DataType.TEXT, index_filterable=True),
            Property(name="doi", data_type=DataType.TEXT, index_filterable=True),
            Property(name="title", data_type=DataType.TEXT, index_searchable=True),
            Property(name="authors", data_type=DataType.TEXT_ARRAY, index_filterable=True),
            Property(name="journal", data_type=DataType.TEXT, index_filterable=True),
            Property(name="year", data_type=DataType.INT, index_filterable=True),
            Property(name="keywords", data_type=DataType.TEXT_ARRAY, index_filterable=True),
            Property(name="section", data_type=DataType.TEXT, index_filterable=True),
            Property(name="chunkIndex", data_type=DataType.INT, index_filterable=True),
            Property(name="content", data_type=DataType.TEXT, index_searchable=True),
            Property(name="offsetStart", data_type=DataType.INT),
            Property(name="offsetEnd", data_type=DataType.INT),
            Property(name="textVersion", data_type=DataType.TEXT, index_filterable=True),
            Property(name="sourceUrl", data_type=DataType.TEXT),
            Property(name="createdAt", data_type=DataType.DATE, index_filterable=True),
        ]
    )
    print(f"Created collection '{COLLECTION_NAME}'")


def get_embedding(client: OpenAI, text: str) -> list[float]:
    """Get embedding for text using OpenAI."""
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text
    )
    return response.data[0].embedding


def seed_papers(weaviate_client: weaviate.WeaviateClient, openai_client: OpenAI) -> int:
    """Seed papers into Weaviate."""
    collection = weaviate_client.collections.get(COLLECTION_NAME)
    total_chunks = 0

    for paper in SAMPLE_PAPERS:
        paper_id = f"pmid:{paper['pmid']}"
        print(f"\nProcessing: {paper['title'][:50]}...")

        for section, content in paper["sections"].items():
            chunk_id = f"{paper_id}|{section}|0"
            chunk_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id))

            # Get embedding
            embedding = get_embedding(openai_client, content)

            # Insert into Weaviate
            collection.data.insert(
                uuid=chunk_uuid,
                properties={
                    "paperId": paper_id,
                    "chunkId": chunk_id,
                    "embeddingVersion": EMBEDDING_VERSION,
                    "pmid": paper["pmid"],
                    "title": paper["title"],
                    "authors": paper["authors"],
                    "journal": paper["journal"],
                    "year": paper["year"],
                    "keywords": paper["keywords"],
                    "section": section,
                    "chunkIndex": 0,
                    "content": content,
                    "offsetStart": 0,
                    "offsetEnd": len(content),
                    "textVersion": "canonical_v1",
                    "sourceUrl": f"https://pubmed.ncbi.nlm.nih.gov/{paper['pmid']}/",
                    "createdAt": datetime.now(timezone.utc),
                },
                vector=embedding
            )
            total_chunks += 1
            print(f"  + {section}")

    return total_chunks


def main():
    print("=" * 60)
    print("Weaviate Seed Script - Test Oncology Data")
    print("=" * 60)

    # Check API key
    if not os.getenv("OPENAI_API_KEY"):
        print("\nError: OPENAI_API_KEY not set")
        return

    # Connect to Weaviate
    print(f"\nConnecting to Weaviate at {WEAVIATE_HOST}:{WEAVIATE_PORT}...")
    weaviate_client = weaviate.connect_to_local(
        host=WEAVIATE_HOST,
        port=WEAVIATE_PORT,
    )

    try:
        # Check connection
        if not weaviate_client.is_ready():
            print("Error: Weaviate is not ready")
            return

        print("Connected!")

        # Create collection
        create_collection(weaviate_client)

        # Initialize OpenAI client
        openai_client = OpenAI()

        # Seed papers
        print("\nSeeding papers...")
        total = seed_papers(weaviate_client, openai_client)

        print(f"\n{'=' * 60}")
        print(f"Done! Inserted {total} chunks from {len(SAMPLE_PAPERS)} papers")
        print(f"{'=' * 60}")

        # Verify
        collection = weaviate_client.collections.get(COLLECTION_NAME)
        count = collection.aggregate.over_all(total_count=True).total_count
        print(f"\nVerification: {count} objects in collection")

    finally:
        weaviate_client.close()


if __name__ == "__main__":
    main()

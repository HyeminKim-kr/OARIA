"""비용 분석: 벡터 DB vs 기존 설계

10만 논문 기준 월간 비용 분석
"""

# ─────────────────────────────────────────────────────────────
# 기본 가정
# ─────────────────────────────────────────────────────────────

NUM_PAPERS = 100_000  # 10만 논문
CHUNKS_PER_PAPER = 30  # 논문당 평균 청크 수
TOTAL_CHUNKS = NUM_PAPERS * CHUNKS_PER_PAPER  # 300만 청크

# 벡터 크기
EMBEDDING_DIM = 1536
BYTES_PER_FLOAT = 4
VECTOR_SIZE_KB = EMBEDDING_DIM * BYTES_PER_FLOAT / 1024  # 6KB

# 텍스트 크기
AVG_CHUNK_TEXT_KB = 2  # 청크당 평균 텍스트 크기
AVG_FULLTEXT_KB = 50   # 논문당 평균 fulltext 크기

print("=" * 60)
print("RAG 시스템 비용 분석 (10만 논문 기준)")
print("=" * 60)

# ─────────────────────────────────────────────────────────────
# 1. 임베딩 비용 (일회성)
# ─────────────────────────────────────────────────────────────

print("\n## 1. 임베딩 비용 (OpenAI, 일회성)")

AVG_TOKENS_PER_CHUNK = 600
TOTAL_TOKENS = TOTAL_CHUNKS * AVG_TOKENS_PER_CHUNK
EMBEDDING_COST_PER_1M = 0.02  # $0.02 / 1M tokens

embedding_cost = (TOTAL_TOKENS / 1_000_000) * EMBEDDING_COST_PER_1M

print(f"   총 청크: {TOTAL_CHUNKS:,}개")
print(f"   총 토큰: {TOTAL_TOKENS:,} ({TOTAL_TOKENS/1_000_000:.1f}M)")
print(f"   비용: ${embedding_cost:.2f} (일회성)")

# ─────────────────────────────────────────────────────────────
# 2. 스토리지 비용 (월간)
# ─────────────────────────────────────────────────────────────

print("\n## 2. 스토리지 비용 (월간)")

# PostgreSQL
pg_size_gb = NUM_PAPERS * 1 / 1024 / 1024  # ~1KB/논문
print(f"\n### PostgreSQL (메타데이터)")
print(f"   용량: {pg_size_gb:.2f} GB")
print(f"   비용: 거의 무시 가능")

# S3
s3_size_gb = NUM_PAPERS * AVG_FULLTEXT_KB / 1024 / 1024
s3_cost_per_gb = 0.023  # AWS S3 Standard
s3_monthly = s3_size_gb * s3_cost_per_gb

print(f"\n### S3 (원본 텍스트)")
print(f"   용량: {s3_size_gb:.2f} GB")
print(f"   비용: ${s3_monthly:.2f}/월")

# Weaviate Self-hosted
weaviate_vector_gb = TOTAL_CHUNKS * VECTOR_SIZE_KB / 1024 / 1024
weaviate_text_gb = TOTAL_CHUNKS * AVG_CHUNK_TEXT_KB / 1024 / 1024
weaviate_total_gb = weaviate_vector_gb + weaviate_text_gb

print(f"\n### Weaviate (Self-hosted)")
print(f"   벡터 용량: {weaviate_vector_gb:.2f} GB")
print(f"   텍스트 용량: {weaviate_text_gb:.2f} GB")
print(f"   총 용량: {weaviate_total_gb:.2f} GB")
print(f"   비용: 서버 비용만 (RAM 필요: ~{weaviate_total_gb * 2:.0f} GB)")

# ─────────────────────────────────────────────────────────────
# 3. 클라우드 벡터 DB 비용 비교
# ─────────────────────────────────────────────────────────────

print("\n## 3. 클라우드 벡터 DB 비용 비교 (월간)")

# Pinecone
pinecone_per_vector_month = 0.00025  # Starter plan estimate
pinecone_monthly = TOTAL_CHUNKS * pinecone_per_vector_month
print(f"\n### Pinecone (Serverless)")
print(f"   {TOTAL_CHUNKS:,} 벡터 기준")
print(f"   비용: ~${pinecone_monthly:.0f}/월")

# Weaviate Cloud
print(f"\n### Weaviate Cloud")
print(f"   Sandbox: 무료 (제한적)")
print(f"   Standard: ~$25/월 + 사용량")
print(f"   Enterprise: 협의")

# Qdrant Cloud
print(f"\n### Qdrant Cloud")
print(f"   Free: 1GB 무료")
print(f"   {weaviate_total_gb:.0f}GB 기준: ~$50-100/월 추정")

# ─────────────────────────────────────────────────────────────
# 4. Self-hosted 서버 비용
# ─────────────────────────────────────────────────────────────

print("\n## 4. Self-hosted 서버 비용 (월간)")

# AWS EC2 예시
print(f"\n### AWS EC2 (Weaviate + PostgreSQL)")
print(f"   필요 RAM: ~{weaviate_total_gb * 2:.0f} GB")
print(f"   권장 인스턴스: r6g.xlarge (32GB RAM)")
print(f"   비용: ~$150/월 (On-Demand)")
print(f"   Reserved: ~$95/월 (1년 약정)")

print(f"\n### 한국 클라우드 (NCP, AWS Seoul)")
print(f"   비슷한 스펙: ~$100-150/월")

# ─────────────────────────────────────────────────────────────
# 5. 총 비용 비교
# ─────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("## 총 비용 비교 (10만 논문, 월간)")
print("=" * 60)

print(f"""
┌────────────────────────────────────────────────────────────┐
│  옵션 A: Self-hosted (현재 설계)                           │
│  - PostgreSQL + S3 + Weaviate (Docker)                    │
│  - 서버: ~$100-150/월                                      │
│  - S3: ~${s3_monthly:.0f}/월                                         │
│  - 총: ~$100-150/월                                        │
├────────────────────────────────────────────────────────────┤
│  옵션 B: 클라우드 벡터 DB                                   │
│  - Pinecone: ~${pinecone_monthly:.0f}/월                               │
│  - Weaviate Cloud: ~$50-200/월 (추정)                     │
│  - + 별도 DB/스토리지 비용                                 │
├────────────────────────────────────────────────────────────┤
│  옵션 C: Weaviate만 사용 (Parent 데이터 포함)              │
│  - 섹션 전체를 Weaviate에 저장                             │
│  - 용량 증가: ~3x                                          │
│  - 서버 비용 증가: ~$200-250/월                            │
└────────────────────────────────────────────────────────────┘
""")

print("## 결론")
print(f"""
1. Self-hosted가 가장 경제적 (~$100-150/월)
2. Pinecone 등 클라우드 벡터 DB는 대용량에서 비용 급증
3. PostgreSQL + S3 유지하면서 Weaviate는 검색용으로만 사용이 최적

권장: 현재 설계 유지 (PostgreSQL + S3 + Weaviate Self-hosted)
- Parent Retrieval은 Weaviate 내에서 처리 (추가 비용 없음)
- S3 방식은 백업/감사용으로만 사용
""")

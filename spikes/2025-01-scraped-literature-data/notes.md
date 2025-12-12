# Spike Notes

## 2025-01-12 - 초기 구현

### 구현 완료

- [x] Docker Compose dual mode (local/gcp)
- [x] FastAPI backend with all endpoints
- [x] PubMed E-utilities client with rate limiting
- [x] ETL worker with batch processing
- [x] Qdrant client for vector search
- [x] PubMedBERT embedding worker
- [x] Next.js frontend (검색, 대시보드, Evidence)

### 테스트 결과

_(실행 후 업데이트)_

### 발견 사항

_(실험 후 업데이트)_

### 다음 단계

- [ ] PMC Full-text 수집 추가
- [ ] Chunking 전략 구현 (300-500 tokens)
- [ ] RAG 파이프라인 구현
- [ ] GCP 배포 테스트

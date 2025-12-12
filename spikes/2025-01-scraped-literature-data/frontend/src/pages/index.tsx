/**
 * OARIA Spike - 메인 검색 페이지
 * 
 * PubMed 논문 검색 및 ETL 시작 UI
 */

import { useState } from 'react';
import Link from 'next/link';

// API URL
const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

interface Paper {
  pmid: string;
  title: string;
  abstract: string;
  authors: string[];
  journal: string;
  pubdate: string;
}

interface SearchResult {
  papers: Paper[];
  total: number;
  term: string;
}

export default function Home() {
  const [term, setTerm] = useState('breast cancer');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [count, setCount] = useState<{ total: number; estimated_hours: number } | null>(null);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [loading, setLoading] = useState(false);
  const [etlLimit, setEtlLimit] = useState(100);
  const [etlJobId, setEtlJobId] = useState<string | null>(null);
  const [etlStatus, setEtlStatus] = useState<string>('');
  const [expanded, setExpanded] = useState<string | null>(null);

  // 검색 건수 조회
  const handleSearch = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ term });
      if (dateFrom) params.append('date_from', dateFrom);
      if (dateTo) params.append('date_to', dateTo);
      
      const res = await fetch(`${API_URL}/api/pubmed/count?${params}`);
      const data = await res.json();
      setCount(data);
      setPapers([]);
    } catch (error) {
      console.error('Search error:', error);
    } finally {
      setLoading(false);
    }
  };

  // 미리보기
  const handlePreview = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/pubmed/preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ term, date_from: dateFrom, date_to: dateTo }),
      });
      const data: SearchResult = await res.json();
      setPapers(data.papers);
      if (!count) {
        setCount({ total: data.total, estimated_hours: 0 });
      }
    } catch (error) {
      console.error('Preview error:', error);
    } finally {
      setLoading(false);
    }
  };

  // ETL 시작
  const handleStartETL = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/etl/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ term, limit: etlLimit, offset: 0 }),
      });
      const data = await res.json();
      setEtlJobId(data.job_id);
      setEtlStatus('running');
      
      // 상태 폴링 시작
      pollETLStatus(data.job_id);
    } catch (error) {
      console.error('ETL start error:', error);
    } finally {
      setLoading(false);
    }
  };

  // ETL 상태 폴링
  const pollETLStatus = async (jobId: string) => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_URL}/api/etl/status?job_id=${jobId}`);
        const data = await res.json();
        setEtlStatus(`${data.status} (${data.collected}/${data.total})`);
        
        if (data.status === 'completed' || data.status === 'error') {
          clearInterval(interval);
        }
      } catch (error) {
        console.error('Status polling error:', error);
        clearInterval(interval);
      }
    }, 2000);
  };

  return (
    <div className="container">
      {/* Header */}
      <header className="header">
        <h1>🔬 OARIA Spike</h1>
        <p>PubMed/PMC ETL → SQL → Embedding → Qdrant</p>
      </header>

      {/* Navigation */}
      <nav>
        <Link href="/" className="active">검색</Link>
        <Link href="/dashboard">대시보드</Link>
        <Link href="/evidence">Evidence</Link>
      </nav>

      {/* Search Form */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 150px 150px auto auto', gap: 12, alignItems: 'end' }}>
          <div>
            <label style={{ display: 'block', marginBottom: 6, fontSize: 14, color: 'var(--text-secondary)' }}>검색어</label>
            <input
              className="input"
              value={term}
              onChange={(e) => setTerm(e.target.value)}
              placeholder="예: breast cancer"
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: 6, fontSize: 14, color: 'var(--text-secondary)' }}>시작일</label>
            <input
              className="input"
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: 6, fontSize: 14, color: 'var(--text-secondary)' }}>종료일</label>
            <input
              className="input"
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
            />
          </div>
          <button className="btn btn-primary" onClick={handleSearch} disabled={loading}>
            {loading ? '⏳' : '🔍'} 검색
          </button>
          <button className="btn btn-secondary" onClick={handlePreview} disabled={loading}>
            👀 미리보기
          </button>
        </div>
      </div>

      {/* Stats */}
      {count && (
        <div className="stats-grid">
          <div className="card stat-card">
            <div className="stat-value">{count.total.toLocaleString()}</div>
            <div className="stat-label">총 논문 수</div>
          </div>
          <div className="card stat-card">
            <div className="stat-value">~{count.estimated_hours.toFixed(2)}h</div>
            <div className="stat-label">예상 수집 시간</div>
          </div>
          <div className="card stat-card">
            <div className="stat-value">{papers.length}</div>
            <div className="stat-label">미리보기</div>
          </div>
        </div>
      )}

      {/* ETL Controls */}
      {count && count.total > 0 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div style={{ marginBottom: 16, padding: 12, background: 'rgba(99, 102, 241, 0.1)', borderRadius: 8 }}>
            💡 무료 API는 초당 3회로 제한됩니다. 대량 수집 시 시간이 걸릴 수 있습니다.
          </div>
          <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
            <div>
              <label style={{ marginRight: 8, fontSize: 14 }}>수집할 논문 수:</label>
              <input
                className="input"
                type="number"
                value={etlLimit}
                onChange={(e) => setEtlLimit(Number(e.target.value))}
                style={{ width: 100 }}
                min={1}
                max={count.total}
              />
            </div>
            <button className="btn btn-primary" onClick={handleStartETL} disabled={loading || etlStatus === 'running'}>
              🚀 ETL 시작
            </button>
            {etlJobId && (
              <span className={`badge ${etlStatus.includes('completed') ? 'badge-completed' : 'badge-running'}`}>
                {etlStatus}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Papers List */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', padding: '16px 0', borderBottom: '1px solid var(--border)' }}>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600 }}>📚 논문 목록</h2>
          <span>{papers.length} 건</span>
        </div>
        
        {papers.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-secondary)' }}>
            <p>검색 또는 미리보기를 클릭하여 논문을 가져오세요</p>
          </div>
        ) : (
          papers.map((paper) => (
            <div
              key={paper.pmid}
              className="paper-card"
              onClick={() => setExpanded(expanded === paper.pmid ? null : paper.pmid)}
            >
              <div className="paper-title">{paper.title}</div>
              <div className="paper-meta">
                <span style={{ marginRight: 16, fontFamily: 'monospace', background: 'var(--bg-secondary)', padding: '2px 8px', borderRadius: 4 }}>
                  PMID: {paper.pmid}
                </span>
                <span style={{ marginRight: 16 }}>📅 {paper.pubdate}</span>
                <span style={{ marginRight: 16 }}>📖 {paper.journal}</span>
                <span>👥 {paper.authors?.slice(0, 3).join(', ')}{(paper.authors?.length || 0) > 3 ? '...' : ''}</span>
              </div>
              {expanded === paper.pmid && (
                <div style={{ marginTop: 12, fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                  {paper.abstract || '(초록 없음)'}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

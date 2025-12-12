/**
 * OARIA Spike - Evidence 페이지
 * 
 * Qdrant 의미 검색 및 RAG 결과 뷰어
 */

import { useState } from 'react';
import Link from 'next/link';

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

interface SearchResult {
  pmid: string;
  title: string;
  abstract: string;
  score: number;
  authors: string[];
  journal: string;
  pubdate: string;
}

interface SemanticSearchResponse {
  query: string;
  results: SearchResult[];
  total: number;
}

export default function Evidence() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastQuery, setLastQuery] = useState('');

  // 의미 검색 실행
  const handleSearch = async () => {
    if (!query.trim()) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const res = await fetch(`${API_URL}/api/search/semantic`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          limit: 20,
          score_threshold: 0.3,
        }),
      });
      
      if (!res.ok) {
        throw new Error('검색 실패. 임베딩이 완료된 논문이 있는지 확인하세요.');
      }
      
      const data: SemanticSearchResponse = await res.json();
      setResults(data.results);
      setLastQuery(data.query);
    } catch (err) {
      setError(err instanceof Error ? err.message : '검색 오류');
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  // 점수에 따른 색상
  const getScoreColor = (score: number) => {
    if (score >= 0.8) return '#10b981';
    if (score >= 0.6) return '#6366f1';
    if (score >= 0.4) return '#f59e0b';
    return '#ef4444';
  };

  return (
    <div className="container">
      {/* Header */}
      <header className="header">
        <h1>🧬 Evidence Search</h1>
        <p>PubMedBERT + Qdrant 의미 검색</p>
      </header>

      {/* Navigation */}
      <nav>
        <Link href="/">검색</Link>
        <Link href="/dashboard">대시보드</Link>
        <Link href="/evidence" className="active">Evidence</Link>
      </nav>

      {/* Search Form */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div style={{ marginBottom: 16 }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 8 }}>의미 검색 (Semantic Search)</h3>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
            자연어 질문을 입력하면 의미적으로 유사한 논문을 찾습니다.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <input
            className="input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="예: What are the treatment options for BRCA1 mutation carriers?"
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            style={{ flex: 1 }}
          />
          <button className="btn btn-primary" onClick={handleSearch} disabled={loading}>
            {loading ? '⏳' : '🔍'} 검색
          </button>
        </div>
        
        {error && (
          <div style={{ marginTop: 12, padding: 12, background: 'rgba(239, 68, 68, 0.1)', borderRadius: 8, color: '#ef4444' }}>
            ⚠️ {error}
          </div>
        )}
      </div>

      {/* Example Queries */}
      <div className="card" style={{ marginBottom: 24 }}>
        <h4 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: 12, color: 'var(--text-secondary)' }}>
          💡 예시 질문
        </h4>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {[
            'breast cancer immunotherapy',
            'BRCA1 mutation treatment',
            'chemotherapy resistance mechanisms',
            'tumor microenvironment',
            'targeted therapy for HER2',
          ].map((example) => (
            <button
              key={example}
              className="btn btn-secondary"
              style={{ fontSize: 12, padding: '8px 12px' }}
              onClick={() => {
                setQuery(example);
              }}
            >
              {example}
            </button>
          ))}
        </div>
      </div>

      {/* Results */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', padding: '16px 0', borderBottom: '1px solid var(--border)' }}>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600 }}>
            📚 검색 결과
            {lastQuery && <span style={{ fontWeight: 400, color: 'var(--text-secondary)', marginLeft: 8 }}>"{lastQuery}"</span>}
          </h2>
          <span>{results.length} 건</span>
        </div>

        {results.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-secondary)' }}>
            {lastQuery ? (
              <p>검색 결과가 없습니다. 다른 쿼리를 시도해보세요.</p>
            ) : (
              <p>검색어를 입력하고 검색 버튼을 클릭하세요.</p>
            )}
          </div>
        ) : (
          results.map((result, index) => (
            <div key={result.pmid} className="paper-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                <span style={{ 
                  fontSize: 12, 
                  fontWeight: 700, 
                  background: 'var(--bg-secondary)', 
                  padding: '4px 12px', 
                  borderRadius: 20 
                }}>
                  #{index + 1}
                </span>
                <span style={{
                  fontSize: 14,
                  fontWeight: 700,
                  color: getScoreColor(result.score),
                }}>
                  유사도: {(result.score * 100).toFixed(1)}%
                </span>
              </div>
              
              <div className="paper-title">{result.title}</div>
              
              <div className="paper-meta" style={{ marginBottom: 12 }}>
                <span style={{ marginRight: 16, fontFamily: 'monospace' }}>PMID: {result.pmid}</span>
                <span style={{ marginRight: 16 }}>📅 {result.pubdate}</span>
                <span style={{ marginRight: 16 }}>📖 {result.journal}</span>
                <span>👥 {result.authors?.slice(0, 2).join(', ')}{(result.authors?.length || 0) > 2 ? '...' : ''}</span>
              </div>
              
              <div style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                {result.abstract}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

/**
 * OARIA Literature - Semantic Search
 * 
 * PubMedBERT + Qdrant 의미 검색
 * Evidence 카드에 신뢰도 색상 표시
 */

import { useState, useEffect } from 'react';
import Link from 'next/link';
import Layout from '../components/Layout';

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

interface EmbeddingStatus {
  pending: number;
  done: number;
  error: number;
  total: number;
}

export default function Evidence() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastQuery, setLastQuery] = useState('');
  const [embeddingStatus, setEmbeddingStatus] = useState<EmbeddingStatus | null>(null);

  useEffect(() => {
    const loadStatus = async () => {
      try {
        const res = await fetch(`${API_URL}/api/embedding/status`);
        if (res.ok) setEmbeddingStatus(await res.json());
      } catch (e) {
        console.error('Status error:', e);
      }
    };
    loadStatus();
  }, []);

  const handleSearch = async () => {
    if (!query.trim()) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const res = await fetch(`${API_URL}/api/search/semantic`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, limit: 20, score_threshold: 0.3 }),
      });
      
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Search failed');
      }
      
      const data = await res.json();
      setResults(data.results);
      setLastQuery(data.query);
    } catch (err: any) {
      setError(err.message || 'Search error');
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  // 신뢰도에 따른 색상 및 레이블
  const getConfidence = (score: number) => {
    if (score >= 0.8) return { color: 'var(--accent-green)', label: 'High', bg: 'rgba(52, 211, 153, 0.15)' };
    if (score >= 0.5) return { color: 'var(--accent-blue)', label: 'Medium', bg: 'rgba(96, 165, 250, 0.15)' };
    return { color: 'var(--text-muted)', label: 'Low', bg: 'var(--bg-tertiary)' };
  };

  const hasEmbeddings = embeddingStatus && embeddingStatus.done > 0;
  const exampleQueries = [
    'breast cancer immunotherapy mechanisms',
    'BRCA1 mutation treatment options',
    'chemotherapy resistance pathways',
    'targeted therapy biomarkers',
  ];

  return (
    <Layout title="Semantic Search" subtitle="AI-powered evidence discovery using PubMedBERT + Qdrant">
      {/* Status Alert */}
      {!hasEmbeddings && (
        <div className="alert alert-warning" style={{ marginBottom: 24 }}>
          <span className="alert-icon">⚠️</span>
          <div className="alert-content">
            No embeddings available. Process embeddings from the{' '}
            <Link href="/dashboard" style={{ color: 'var(--warning)', fontWeight: 600 }}>Papers page</Link>{' '}
            to enable semantic search.
          </div>
        </div>
      )}

      {/* Search Card */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <div className="card-title">
            <span>🔍</span> Search Query
          </div>
          {embeddingStatus && (
            <span className={`badge ${hasEmbeddings ? 'badge-completed' : 'badge-pending'}`}>
              {embeddingStatus.done} embeddings ready
            </span>
          )}
        </div>
        
        <div style={{ display: 'flex', gap: 12 }}>
          <div className="search-input-wrapper" style={{ flex: 1 }}>
            <span className="search-icon">🔬</span>
            <input
              className="input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Enter your research question..."
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              disabled={!hasEmbeddings}
            />
          </div>
          <button 
            className="btn btn-primary" 
            onClick={handleSearch} 
            disabled={loading || !hasEmbeddings}
          >
            {loading ? '⏳ Searching...' : '🔍 Search'}
          </button>
        </div>
        
        {error && (
          <div className="alert alert-error" style={{ marginTop: 16, marginBottom: 0 }}>
            <span className="alert-icon">❌</span>
            <div className="alert-content">{error}</div>
          </div>
        )}
      </div>

      {/* Example Queries */}
      {hasEmbeddings && !lastQuery && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header">
            <div className="card-title">
              <span>💡</span> Example Queries
            </div>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {exampleQueries.map((example) => (
              <button
                key={example}
                className="btn btn-secondary"
                style={{ fontSize: 13 }}
                onClick={() => setQuery(example)}
              >
                {example}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Results */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <span>📊</span> Results
            {lastQuery && (
              <span style={{ fontWeight: 400, fontSize: 13, color: 'var(--text-muted)', marginLeft: 8 }}>
                "{lastQuery}"
              </span>
            )}
          </div>
          <span style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
            {results.length} matches
          </span>
        </div>

        {!hasEmbeddings ? (
          <div className="empty-state">
            <div className="empty-state-icon">🔐</div>
            <div className="empty-state-title">Embeddings Required</div>
            <div className="empty-state-description">
              Process paper embeddings to enable semantic search capabilities.
            </div>
            <Link href="/dashboard">
              <button className="btn btn-primary" style={{ marginTop: 16 }}>
                Go to Papers →
              </button>
            </Link>
          </div>
        ) : results.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">🔍</div>
            <div className="empty-state-title">
              {lastQuery ? 'No results found' : 'Enter a search query'}
            </div>
            <div className="empty-state-description">
              {lastQuery 
                ? 'Try different keywords or a broader query.'
                : 'Use natural language to find relevant research papers.'}
            </div>
          </div>
        ) : (
          results.map((result, index) => {
            const confidence = getConfidence(result.score);
            return (
              <div 
                key={result.pmid} 
                className="paper-card"
                style={{ 
                  borderLeft: `3px solid ${confidence.color}`,
                  paddingLeft: 20,
                }}
              >
                <div style={{ 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'flex-start',
                  marginBottom: 8,
                }}>
                  <span style={{ 
                    fontSize: 12, 
                    fontWeight: 600, 
                    color: 'var(--text-muted)',
                    background: 'var(--bg-tertiary)',
                    padding: '4px 10px',
                    borderRadius: 12,
                  }}>
                    #{index + 1}
                  </span>
                  <div style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: 12,
                  }}>
                    <span style={{ 
                      fontSize: 12, 
                      fontWeight: 600, 
                      color: confidence.color,
                      background: confidence.bg,
                      padding: '4px 12px',
                      borderRadius: 12,
                    }}>
                      {confidence.label} ({(result.score * 100).toFixed(0)}%)
                    </span>
                  </div>
                </div>
                
                <div className="paper-title">{result.title}</div>
                <div className="paper-meta" style={{ marginBottom: 12 }}>
                  <span className="paper-meta-item">
                    <span>🆔</span> {result.pmid}
                  </span>
                  <span className="paper-meta-item">
                    <span>📅</span> {result.pubdate}
                  </span>
                  <span className="paper-meta-item">
                    <span>📖</span> {result.journal}
                  </span>
                </div>
                <div className="paper-abstract">{result.abstract}</div>
              </div>
            );
          })
        )}
      </div>
    </Layout>
  );
}

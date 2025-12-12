/**
 * OARIA Spike - ETL 대시보드
 * 
 * 저장된 논문, 임베딩 상태, ETL 현황을 보여줍니다.
 */

import { useState, useEffect } from 'react';
import Link from 'next/link';

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

interface Paper {
  pmid: string;
  title: string;
  abstract: string;
  authors: string[];
  journal: string;
  pubdate: string;
  embedding_status: string;
}

interface EmbeddingStatus {
  pending: number;
  processing: number;
  done: number;
  error: number;
  total: number;
}

export default function Dashboard() {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [totalPapers, setTotalPapers] = useState(0);
  const [page, setPage] = useState(1);
  const [embeddingStatus, setEmbeddingStatus] = useState<EmbeddingStatus | null>(null);
  const [loading, setLoading] = useState(false);

  // 논문 목록 로드
  const loadPapers = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/papers?page=${page}&per_page=20`);
      const data = await res.json();
      setPapers(data.papers);
      setTotalPapers(data.total);
    } catch (error) {
      console.error('Load papers error:', error);
    } finally {
      setLoading(false);
    }
  };

  // 임베딩 상태 로드
  const loadEmbeddingStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/api/embedding/status`);
      const data = await res.json();
      setEmbeddingStatus(data);
    } catch (error) {
      console.error('Embedding status error:', error);
    }
  };

  // 임베딩 처리
  const processEmbeddings = async () => {
    setLoading(true);
    try {
      await fetch(`${API_URL}/api/embedding/process?batch_size=10`, { method: 'POST' });
      await loadEmbeddingStatus();
      await loadPapers();
    } catch (error) {
      console.error('Process embeddings error:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPapers();
    loadEmbeddingStatus();
  }, [page]);

  // 자동 새로고침
  useEffect(() => {
    const interval = setInterval(() => {
      loadEmbeddingStatus();
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="container">
      {/* Header */}
      <header className="header">
        <h1>📊 대시보드</h1>
        <p>저장된 논문 및 임베딩 상태</p>
      </header>

      {/* Navigation */}
      <nav>
        <Link href="/">검색</Link>
        <Link href="/dashboard" className="active">대시보드</Link>
        <Link href="/evidence">Evidence</Link>
      </nav>

      {/* Stats */}
      <div className="stats-grid">
        <div className="card stat-card">
          <div className="stat-value">{totalPapers.toLocaleString()}</div>
          <div className="stat-label">저장된 논문</div>
        </div>
        <div className="card stat-card">
          <div className="stat-value" style={{ color: '#10b981' }}>{embeddingStatus?.done || 0}</div>
          <div className="stat-label">임베딩 완료</div>
        </div>
        <div className="card stat-card">
          <div className="stat-value" style={{ color: '#f59e0b' }}>{embeddingStatus?.pending || 0}</div>
          <div className="stat-label">대기 중</div>
        </div>
        <div className="card stat-card">
          <div className="stat-value" style={{ color: '#ef4444' }}>{embeddingStatus?.error || 0}</div>
          <div className="stat-label">오류</div>
        </div>
      </div>

      {/* Embedding Progress */}
      {embeddingStatus && embeddingStatus.total > 0 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>임베딩 진행률</h3>
            <button className="btn btn-secondary" onClick={processEmbeddings} disabled={loading}>
              ⚡ 임베딩 처리 (10건)
            </button>
          </div>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${(embeddingStatus.done / embeddingStatus.total) * 100}%` }}
            />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 14, color: 'var(--text-secondary)' }}>
            <span>{embeddingStatus.done} / {embeddingStatus.total}</span>
            <span>{((embeddingStatus.done / embeddingStatus.total) * 100).toFixed(1)}%</span>
          </div>
        </div>
      )}

      {/* Papers Table */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', padding: '16px 0', borderBottom: '1px solid var(--border)' }}>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600 }}>📚 저장된 논문</h2>
          <button className="btn btn-secondary" onClick={loadPapers} disabled={loading}>
            🔄 새로고침
          </button>
        </div>

        {papers.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-secondary)' }}>
            <p>저장된 논문이 없습니다. ETL을 실행하세요.</p>
          </div>
        ) : (
          <>
            {papers.map((paper) => (
              <div key={paper.pmid} className="paper-card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div style={{ flex: 1 }}>
                    <div className="paper-title">{paper.title}</div>
                    <div className="paper-meta">
                      <span style={{ marginRight: 16, fontFamily: 'monospace' }}>PMID: {paper.pmid}</span>
                      <span style={{ marginRight: 16 }}>📅 {paper.pubdate}</span>
                      <span>📖 {paper.journal}</span>
                    </div>
                  </div>
                  <span className={`badge ${
                    paper.embedding_status === 'done' ? 'badge-completed' :
                    paper.embedding_status === 'error' ? 'badge-error' : 'badge-running'
                  }`}>
                    {paper.embedding_status}
                  </span>
                </div>
              </div>
            ))}

            {/* Pagination */}
            <div style={{ display: 'flex', justifyContent: 'center', gap: 8, padding: 16 }}>
              <button
                className="btn btn-secondary"
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                ← 이전
              </button>
              <span style={{ padding: '12px 16px', color: 'var(--text-secondary)' }}>
                {page} / {Math.ceil(totalPapers / 20)}
              </span>
              <button
                className="btn btn-secondary"
                onClick={() => setPage(p => p + 1)}
                disabled={page >= Math.ceil(totalPapers / 20)}
              >
                다음 →
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

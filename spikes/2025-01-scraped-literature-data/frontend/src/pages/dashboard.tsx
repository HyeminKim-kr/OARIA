/**
 * OARIA Literature - Papers Management
 * 
 * 논문 목록 관리 및 임베딩 처리
 */

import { useState, useEffect } from 'react';
import Link from 'next/link';
import Layout from '../components/Layout';

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
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(1);
  const [perPage] = useState(20);
  const [embeddingStatus, setEmbeddingStatus] = useState<EmbeddingStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  const loadPapers = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/papers?page=${page}&per_page=${perPage}`);
      const data = await res.json();
      setPapers(data.papers || []);
      setTotalPapers(data.total || 0);
      setTotalPages(data.total_pages || 1);
      setError(null);
    } catch (err) {
      console.error('Load papers error:', err);
      setError('Failed to load papers');
    } finally {
      setLoading(false);
    }
  };

  const loadEmbeddingStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/api/embedding/status`);
      if (res.ok) setEmbeddingStatus(await res.json());
    } catch (err) {
      console.error('Embedding status error:', err);
    }
  };

  const processEmbeddings = async (batchSize: number = 10) => {
    setProcessing(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/embedding/process?batch_size=${batchSize}`, { method: 'POST' });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Processing failed');
      }
      await loadEmbeddingStatus();
      await loadPapers();
    } catch (err: any) {
      setError(err.message || 'Processing error');
    } finally {
      setProcessing(false);
    }
  };

  const processAllEmbeddings = async () => {
    if (!embeddingStatus || embeddingStatus.pending === 0) return;
    setProcessing(true);
    setError(null);
    
    const totalBatches = Math.ceil(embeddingStatus.pending / 10);
    for (let i = 0; i < totalBatches; i++) {
      try {
        const res = await fetch(`${API_URL}/api/embedding/process?batch_size=10`, { method: 'POST' });
        if (!res.ok) throw new Error('Batch failed');
        await loadEmbeddingStatus();
        await new Promise(r => setTimeout(r, 100));
      } catch (err: any) {
        setError(err.message);
        break;
      }
    }
    
    await loadPapers();
    setProcessing(false);
  };

  useEffect(() => {
    loadPapers();
    loadEmbeddingStatus();
  }, [page]);

  useEffect(() => {
    const interval = setInterval(loadEmbeddingStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const progress = embeddingStatus?.total 
    ? (embeddingStatus.done / embeddingStatus.total) * 100 
    : 0;

  return (
    <Layout title="Papers" subtitle="Manage papers and embeddings">
      {/* Error Alert */}
      {error && (
        <div className="alert alert-error" style={{ marginBottom: 24 }}>
          <span className="alert-icon">⚠️</span>
          <div className="alert-content">{error}</div>
          <button className="alert-close" onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {/* Stats */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Total Papers</div>
          <div className="stat-value">{totalPapers.toLocaleString()}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Embeddings Done</div>
          <div className="stat-value green">{embeddingStatus?.done || 0}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Pending</div>
          <div className="stat-value yellow">{embeddingStatus?.pending || 0}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Errors</div>
          <div className="stat-value red">{embeddingStatus?.error || 0}</div>
        </div>
      </div>

      {/* Embedding Controls */}
      {embeddingStatus && embeddingStatus.total > 0 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header">
            <div className="card-title">
              <span>🧠</span> Embedding Progress
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button 
                className="btn btn-secondary" 
                onClick={() => processEmbeddings(10)} 
                disabled={processing || embeddingStatus.pending === 0}
              >
                {processing ? '⏳' : '⚡'} Process 10
              </button>
              <button 
                className="btn btn-primary" 
                onClick={processAllEmbeddings} 
                disabled={processing || embeddingStatus.pending === 0}
              >
                {processing ? '⏳ Processing...' : `🚀 Process All (${embeddingStatus.pending})`}
              </button>
            </div>
          </div>
          <div className="progress-bar" style={{ marginBottom: 12 }}>
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, color: 'var(--text-secondary)' }}>
            <span>{embeddingStatus.done} / {embeddingStatus.total} completed</span>
            <span>{progress.toFixed(1)}%</span>
          </div>
        </div>
      )}

      {/* Papers Table */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <span>📚</span> Papers
            <span style={{ 
              fontWeight: 400, 
              fontSize: 13, 
              color: 'var(--text-muted)', 
              marginLeft: 8 
            }}>
              Page {page} of {totalPages}
            </span>
          </div>
          <button className="btn btn-ghost" onClick={loadPapers} disabled={loading}>
            {loading ? '⏳' : '🔄'} Refresh
          </button>
        </div>

        {papers.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📭</div>
            <div className="empty-state-title">No papers found</div>
            <div className="empty-state-description">
              Run ETL from the <Link href="/" style={{ color: 'var(--accent-green)' }}>dashboard</Link> to collect papers.
            </div>
          </div>
        ) : (
          <>
            {/* Table Header */}
            <div 
              className="table-row table-header"
              style={{ gridTemplateColumns: '100px 1fr 140px 100px' }}
            >
              <div>PMID</div>
              <div>Title</div>
              <div>Journal</div>
              <div>Status</div>
            </div>
            
            {/* Table Rows */}
            {papers.map((paper) => (
              <div 
                key={paper.pmid}
                className="table-row"
                style={{ 
                  gridTemplateColumns: '100px 1fr 140px 100px',
                  cursor: 'pointer',
                }}
                onClick={() => setExpanded(expanded === paper.pmid ? null : paper.pmid)}
              >
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-muted)' }}>
                  {paper.pmid}
                </div>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 4 }}>
                    {paper.title}
                  </div>
                  {expanded === paper.pmid && paper.abstract && (
                    <div style={{ 
                      fontSize: 13, 
                      color: 'var(--text-secondary)', 
                      lineHeight: 1.6,
                      marginTop: 8,
                      padding: 12,
                      background: 'var(--bg-tertiary)',
                      borderRadius: 8,
                    }}>
                      {paper.abstract}
                    </div>
                  )}
                </div>
                <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                  {paper.journal}
                </div>
                <div>
                  <span className={`badge ${
                    paper.embedding_status === 'done' ? 'badge-completed' :
                    paper.embedding_status === 'error' ? 'badge-error' : 'badge-pending'
                  }`}>
                    {paper.embedding_status || 'pending'}
                  </span>
                </div>
              </div>
            ))}

            {/* Pagination */}
            <div className="pagination">
              <button
                className="pagination-btn"
                onClick={() => setPage(1)}
                disabled={page === 1}
              >
                ««
              </button>
              <button
                className="pagination-btn"
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                ←
              </button>
              
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                const pageNum = Math.max(1, Math.min(page - 2, totalPages - 4)) + i;
                if (pageNum > totalPages) return null;
                return (
                  <button
                    key={pageNum}
                    className={`pagination-btn ${pageNum === page ? 'active' : ''}`}
                    onClick={() => setPage(pageNum)}
                  >
                    {pageNum}
                  </button>
                );
              })}
              
              <button
                className="pagination-btn"
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
              >
                →
              </button>
              <button
                className="pagination-btn"
                onClick={() => setPage(totalPages)}
                disabled={page >= totalPages}
              >
                »»
              </button>
            </div>
          </>
        )}
      </div>
    </Layout>
  );
}

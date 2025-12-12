/**
 * OARIA Literature - Dashboard (Home)
 * 
 * 오늘 처리된 논문 / Embedding 상태 / ETL 진행률
 * ETL 워커 컨트롤 포함
 */

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import Layout from '../components/Layout';

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

interface Stats {
  papers: number;
  embeddings: {
    pending: number;
    done: number;
    error: number;
    total: number;
  };
  qdrant_points: number;
}

interface Paper {
  pmid: string;
  title: string;
  journal: string;
  pubdate: string;
  embedding_status: string;
}

interface ETLStatus {
  job_id: string;
  status: string;
  progress: number;
  collected: number;
  total: number;
  message: string;
}

export default function Home() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [recentPapers, setRecentPapers] = useState<Paper[]>([]);
  const [loading, setLoading] = useState(true);
  
  // ETL Worker States
  const [term, setTerm] = useState('breast cancer');
  const [etlLimit, setEtlLimit] = useState(100);
  const [etlOffset, setEtlOffset] = useState(0);
  const [etlStatus, setEtlStatus] = useState<ETLStatus | null>(null);
  const [etlLoading, setEtlLoading] = useState(false);
  const [searchCount, setSearchCount] = useState<number | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const loadData = async () => {
    try {
      const [statsRes, papersRes] = await Promise.all([
        fetch(`${API_URL}/api/db/stats`),
        fetch(`${API_URL}/api/papers?page=1&per_page=5`),
      ]);
      
      if (statsRes.ok) setStats(await statsRes.json());
      if (papersRes.ok) {
        const data = await papersRes.json();
        setRecentPapers(data.papers || []);
      }
    } catch (e) {
      console.error('Load data error:', e);
    } finally {
      setLoading(false);
    }
  };

  const loadSearchCount = async () => {
    if (!term.trim()) return;
    try {
      const res = await fetch(`${API_URL}/api/pubmed/count?term=${encodeURIComponent(term)}`);
      if (res.ok) {
        const data = await res.json();
        setSearchCount(data.count);
      }
    } catch (e) {
      console.error('Search count error:', e);
    }
  };

  const handleStartETL = async () => {
    setEtlLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/etl/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ term, limit: etlLimit, offset: etlOffset }),
      });
      const data = await res.json();
      setEtlStatus({ job_id: data.job_id, status: 'running', progress: 0, collected: 0, total: etlLimit, message: '' });
      pollETLStatus(data.job_id);
    } catch (error) {
      console.error('ETL start error:', error);
    } finally {
      setEtlLoading(false);
    }
  };

  const pollETLStatus = (jobId: string) => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    
    intervalRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_URL}/api/etl/status?job_id=${jobId}`);
        if (!res.ok) {
          if (intervalRef.current) clearInterval(intervalRef.current);
          setEtlStatus(null);
          return;
        }
        const data: ETLStatus = await res.json();
        setEtlStatus(data);
        
        if (data.status === 'completed' || data.status === 'error' || data.status === 'stopped') {
          if (intervalRef.current) clearInterval(intervalRef.current);
          loadData();
          if (data.status === 'completed') {
            setTimeout(() => setEtlStatus(null), 5000);
          }
        }
      } catch (error) {
        console.error('Status polling error:', error);
        if (intervalRef.current) clearInterval(intervalRef.current);
        setEtlStatus(null);
      }
    }, 1000);
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => {
      clearInterval(interval);
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  useEffect(() => {
    const debounce = setTimeout(loadSearchCount, 500);
    return () => clearTimeout(debounce);
  }, [term]);

  const embeddingProgress = stats?.embeddings 
    ? (stats.embeddings.done / Math.max(stats.embeddings.total, 1)) * 100 
    : 0;

  const isETLRunning = etlStatus && etlStatus.status === 'running';

  return (
    <Layout title="Dashboard" subtitle="OARIA Literature Data System Overview">
      {/* ETL Worker Card */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <div className="card-title">
            <span>🚀</span> ETL Worker
          </div>
          {searchCount !== null && (
            <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              {searchCount.toLocaleString()} results in PubMed
            </span>
          )}
        </div>
        
        <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
          <div style={{ flex: 2, minWidth: 200 }}>
            <input
              className="input"
              value={term}
              onChange={(e) => setTerm(e.target.value)}
              placeholder="Search term (e.g., breast cancer)"
              disabled={isETLRunning}
            />
          </div>
          <div style={{ width: 100 }}>
            <input
              className="input"
              type="number"
              value={etlLimit}
              onChange={(e) => setEtlLimit(Math.max(1, parseInt(e.target.value) || 100))}
              placeholder="Limit"
              disabled={isETLRunning}
            />
          </div>
          <div style={{ width: 100 }}>
            <input
              className="input"
              type="number"
              value={etlOffset}
              onChange={(e) => setEtlOffset(Math.max(0, parseInt(e.target.value) || 0))}
              placeholder="Offset"
              disabled={isETLRunning}
            />
          </div>
          <button 
            className="btn btn-primary"
            onClick={handleStartETL}
            disabled={etlLoading || isETLRunning || !term.trim()}
          >
            {isETLRunning ? '⏳ Running...' : '▶️ Start ETL'}
          </button>
        </div>

        {/* ETL Progress */}
        {etlStatus && (
          <div style={{ 
            padding: 16, 
            background: 'var(--bg-tertiary)', 
            borderRadius: 12,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <span className={`badge ${
                etlStatus.status === 'running' ? 'badge-running' :
                etlStatus.status === 'completed' ? 'badge-completed' : 'badge-error'
              }`}>
                {etlStatus.status}
              </span>
              <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                {etlStatus.collected} / {etlStatus.total} papers
              </span>
            </div>
            <div className="progress-bar" style={{ marginBottom: 8 }}>
              <div className="progress-fill" style={{ width: `${etlStatus.progress}%` }} />
            </div>
            {etlStatus.message && (
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                {etlStatus.message}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Stats Grid */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Total Papers</div>
          <div className="stat-value">{stats?.papers?.toLocaleString() || '—'}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Embeddings Done</div>
          <div className="stat-value green">{stats?.embeddings?.done?.toLocaleString() || '—'}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Pending</div>
          <div className="stat-value yellow">{stats?.embeddings?.pending?.toLocaleString() || '—'}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Qdrant Points</div>
          <div className="stat-value blue">{stats?.qdrant_points?.toLocaleString() || '—'}</div>
        </div>
      </div>

      {/* Embedding Progress */}
      {stats?.embeddings && stats.embeddings.total > 0 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header">
            <div className="card-title">
              <span>🧠</span> Embedding Progress
            </div>
            <span style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
              {embeddingProgress.toFixed(1)}%
            </span>
          </div>
          <div className="progress-bar" style={{ marginBottom: 16 }}>
            <div className="progress-fill" style={{ width: `${embeddingProgress}%` }} />
          </div>
          <div style={{ display: 'flex', gap: 24, fontSize: 13, color: 'var(--text-secondary)' }}>
            <span>✅ Done: {stats.embeddings.done}</span>
            <span>⏳ Pending: {stats.embeddings.pending}</span>
            {stats.embeddings.error > 0 && <span>❌ Errors: {stats.embeddings.error}</span>}
          </div>
        </div>
      )}

      {/* Quick Actions */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <div className="card-title">
            <span>⚡</span> Quick Actions
          </div>
        </div>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <Link href="/dashboard">
            <button className="btn btn-primary">📊 Manage Papers</button>
          </Link>
          <Link href="/evidence">
            <button className="btn btn-secondary">🔍 Semantic Search</button>
          </Link>
          <Link href="/guide">
            <button className="btn btn-ghost">📖 View Guide</button>
          </Link>
        </div>
      </div>

      {/* Recent Papers */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <span>📚</span> Recent Papers
          </div>
          <Link href="/dashboard">
            <button className="btn btn-ghost" style={{ fontSize: 13 }}>View All →</button>
          </Link>
        </div>
        
        {recentPapers.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📭</div>
            <div className="empty-state-title">No papers yet</div>
            <div className="empty-state-description">
              Start by running an ETL job to collect papers from PubMed.
            </div>
          </div>
        ) : (
          recentPapers.map((paper) => (
            <div key={paper.pmid} className="paper-card">
              <div className="paper-title">{paper.title}</div>
              <div className="paper-meta">
                <span className="paper-meta-item">
                  <span>🆔</span> {paper.pmid}
                </span>
                <span className="paper-meta-item">
                  <span>📅</span> {paper.pubdate}
                </span>
                <span className="paper-meta-item">
                  <span>📖</span> {paper.journal}
                </span>
                <span className={`badge ${
                  paper.embedding_status === 'done' ? 'badge-completed' :
                  paper.embedding_status === 'error' ? 'badge-error' : 'badge-pending'
                }`}>
                  {paper.embedding_status || 'pending'}
                </span>
              </div>
            </div>
          ))
        )}
      </div>
    </Layout>
  );
}

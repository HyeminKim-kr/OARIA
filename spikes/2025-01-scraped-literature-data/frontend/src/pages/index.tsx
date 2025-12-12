/**
 * OARIA Literature - Dashboard (Home)
 * 
 * 오늘 처리된 논문 / Embedding 상태 / ETL 진행률
 */

import { useState, useEffect } from 'react';
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

export default function Home() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [recentPapers, setRecentPapers] = useState<Paper[]>([]);
  const [loading, setLoading] = useState(true);

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

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, []);

  const embeddingProgress = stats?.embeddings 
    ? (stats.embeddings.done / Math.max(stats.embeddings.total, 1)) * 100 
    : 0;

  return (
    <Layout title="Dashboard" subtitle="OARIA Literature Data System Overview">
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

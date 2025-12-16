/**
 * OARIA Literature - Guide Page
 * 
 * 시스템 흐름 및 가이드
 */

import { useState, useEffect } from 'react';
import Link from 'next/link';
import Layout from '../components/Layout';

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

interface Stats {
  papers: number;
  embeddings: { done: number; pending: number; total: number };
}

export default function Guide() {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    const loadStats = async () => {
      try {
        const [papersRes, embeddingRes] = await Promise.all([
          fetch(`${API_URL}/api/papers?page=1&per_page=1`),
          fetch(`${API_URL}/api/embedding/status`),
        ]);
        
        const papersData = papersRes.ok ? await papersRes.json() : { total: 0 };
        const embeddingData = embeddingRes.ok ? await embeddingRes.json() : { done: 0, pending: 0, total: 0 };
        
        setStats({
          papers: papersData.total || 0,
          embeddings: embeddingData,
        });
      } catch (e) {
        console.error('Stats error:', e);
      }
    };
    loadStats();
  }, []);

  const steps = [
    { 
      num: 1, 
      icon: '📚',
      title: 'Collect Papers', 
      desc: 'Search and fetch papers from PubMed using ETL pipeline',
      action: 'Go to Dashboard', 
      link: '/', 
      done: stats ? stats.papers > 0 : false,
    },
    { 
      num: 2, 
      icon: '🧠',
      title: 'Generate Embeddings', 
      desc: 'Convert paper abstracts to vectors using PubMedBERT',
      action: 'Process Embeddings', 
      link: '/dashboard', 
      done: stats ? stats.embeddings.done > 0 : false,
    },
    { 
      num: 3, 
      icon: '🔍',
      title: 'Semantic Search', 
      desc: 'Query papers using natural language and Qdrant vector search',
      action: 'Start Searching', 
      link: '/evidence', 
      done: false,
    },
  ];

  return (
    <Layout title="Guide" subtitle="Getting started with OARIA Literature">
      {/* Current Status */}
      {stats && (
        <div className="stats-grid" style={{ marginBottom: 32 }}>
          <div className="stat-card">
            <div className="stat-label">Papers Collected</div>
            <div className="stat-value">{stats.papers.toLocaleString()}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Embeddings Ready</div>
            <div className="stat-value green">{stats.embeddings.done.toLocaleString()}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Pending Processing</div>
            <div className="stat-value yellow">{stats.embeddings.pending.toLocaleString()}</div>
          </div>
        </div>
      )}

      {/* Getting Started */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <div className="card-title">
            <span>🚀</span> Getting Started
          </div>
        </div>
        
        {steps.map((step, i) => (
          <div 
            key={step.num}
            style={{ 
              display: 'flex', 
              alignItems: 'flex-start', 
              gap: 20, 
              padding: 24,
              borderBottom: i < steps.length - 1 ? '1px solid var(--border-subtle)' : 'none',
              opacity: step.done ? 0.7 : 1,
            }}
          >
            <div style={{ 
              width: 56, 
              height: 56, 
              borderRadius: 16, 
              background: step.done 
                ? 'var(--accent-green)' 
                : 'linear-gradient(135deg, var(--accent-green), var(--accent-blue))',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 24,
              flexShrink: 0,
              color: step.done ? '#0D1117' : 'white',
            }}>
              {step.done ? '✓' : step.icon}
            </div>
            
            <div style={{ flex: 1 }}>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: 12,
                marginBottom: 6,
              }}>
                <h3 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>
                  Step {step.num}: {step.title}
                </h3>
                {step.done && (
                  <span className="badge badge-completed">Completed</span>
                )}
              </div>
              <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                {step.desc}
              </p>
            </div>
            
            <Link href={step.link}>
              <button className={`btn ${step.done ? 'btn-ghost' : 'btn-primary'}`}>
                {step.action} →
              </button>
            </Link>
          </div>
        ))}
      </div>

      {/* Architecture */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <div className="card-title">
            <span>🏗️</span> System Architecture
          </div>
        </div>
        <div style={{ 
          background: 'var(--bg-tertiary)', 
          padding: 24, 
          borderRadius: 12, 
          fontFamily: 'var(--font-mono)',
          fontSize: 13,
          lineHeight: 1.8,
          color: 'var(--text-secondary)',
          overflow: 'auto',
        }}>
          <pre style={{ margin: 0 }}>
{`┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   PubMed    │ ──► │  ETL Worker  │ ──► │  PostgreSQL  │
│   (API)     │     │  (Python)    │     │    (DB)      │
└─────────────┘     └──────────────┘     └──────┬───────┘
                                                │
                    ┌──────────────┐             │
                    │   Qdrant     │ ◄───────────┤
                    │  (Vectors)   │             │
                    └──────┬───────┘             │
                           │                     │
                           ▼                     ▼
                    ┌──────────────┐     ┌──────────────┐
                    │   Semantic   │     │   Embedding  │
                    │    Search    │ ◄── │    Worker    │
                    └──────────────┘     └──────────────┘`}
          </pre>
        </div>
      </div>

      {/* Tech Stack */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <span>🛠️</span> Technology Stack
          </div>
        </div>
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: 16 
        }}>
          {[
            { icon: '⚡', name: 'FastAPI', desc: 'Backend API' },
            { icon: '⚛️', name: 'Next.js', desc: 'Frontend' },
            { icon: '🐘', name: 'PostgreSQL', desc: 'Paper Storage' },
            { icon: '🧠', name: 'PubMedBERT', desc: 'Embeddings' },
            { icon: '🎯', name: 'Qdrant', desc: 'Vector Search' },
            { icon: '🐳', name: 'Docker', desc: 'Deployment' },
          ].map((tech) => (
            <div 
              key={tech.name}
              style={{ 
                padding: 16, 
                background: 'var(--bg-tertiary)', 
                borderRadius: 12,
                display: 'flex',
                alignItems: 'center',
                gap: 12,
              }}
            >
              <span style={{ fontSize: 24 }}>{tech.icon}</span>
              <div>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{tech.name}</div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{tech.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </Layout>
  );
}

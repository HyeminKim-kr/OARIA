/**
 * RAG Search Result Comparison View
 * 
 * Query → Top-K 검색 결과를 비교하여
 * Score / Payload / Abstract / Vector 미리보기를 한 화면에서 검증
 */

import { useState } from 'react';
import Layout from '../components/Layout';

interface RagResult {
  id: string | number;
  score: number;
  payload: {
    title?: string;
    abstract?: string;
    pmid?: string | number;
    [key: string]: any;
  };
  vector?: number[];
}

export default function RagCompareView() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<RagResult[]>([]);
  const [selected, setSelected] = useState<RagResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [limit, setLimit] = useState(5);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setSelected(null);

    try {
      const res = await fetch('/api/rag/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          limit,
        }),
      });

      const data = await res.json();
      setResults(data.results || []);
    } catch (e) {
      console.error(e);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const renderVectorPreview = (vec?: number[]) => {
    if (!vec || vec.length === 0) return 'No vector data';
    const preview = vec.slice(0, 8).map(v => v.toFixed(4)).join(', ');
    return `[${preview}, ... total ${vec.length} dims]`;
  };

  // Score에 따른 색상 그라디언트
  const getScoreColor = (score: number) => {
    if (score >= 0.85) return 'var(--accent-green)';
    if (score >= 0.7) return 'var(--accent-blue)';
    if (score >= 0.5) return 'var(--warning)';
    return 'var(--text-muted)';
  };

  return (
    <Layout title="RAG Result Comparison" subtitle="Query → Top-K Semantic Search Validation">
      {/* Query Input */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            className="input"
            placeholder="Enter natural language query (e.g., 'CRISPR gene therapy mechanisms')..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            style={{ flex: 1, minWidth: 300 }}
          />
          
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <label style={{ fontSize: 13, color: 'var(--text-muted)' }}>Top-K:</label>
            <select
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              style={{
                padding: '10px 12px',
                borderRadius: 8,
                border: '1px solid var(--border-primary)',
                background: 'var(--bg-tertiary)',
                color: 'var(--text-primary)',
                fontSize: 14,
              }}
            >
              <option value={3}>3</option>
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={20}>20</option>
            </select>
          </div>

          <button className="btn btn-primary" onClick={handleSearch} disabled={loading || !query.trim()}>
            🔍 Search
          </button>
        </div>

        {/* Current Query Display */}
        {query && results.length > 0 && (
          <div style={{ 
            marginTop: 16, 
            padding: 12, 
            background: 'var(--bg-tertiary)', 
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            gap: 8
          }}>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>QUERY:</span>
            <span style={{ fontSize: 14, color: 'var(--accent-blue)', fontWeight: 500 }}>{query}</span>
            <span style={{ 
              marginLeft: 'auto', 
              fontSize: 12, 
              color: 'var(--text-muted)',
              background: 'var(--bg-secondary)',
              padding: '4px 10px',
              borderRadius: 12
            }}>
              {results.length} results
            </span>
          </div>
        )}
      </div>

      {/* Results */}
      <div style={{ display: 'grid', gridTemplateColumns: selected ? '1fr 1fr' : '1fr', gap: 24 }}>
        {/* Result List */}
        <div className="card" style={{ overflow: 'hidden' }}>
          <div className="card-header">
            <div className="card-title">📊 Top-K Results</div>
          </div>

          {loading ? (
            <div className="empty-state" style={{ padding: 60 }}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>⏳</div>
              <div>Searching semantic space...</div>
            </div>
          ) : results.length === 0 ? (
            <div className="empty-state" style={{ padding: 60 }}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>🔍</div>
              <div style={{ color: 'var(--text-muted)' }}>
                Enter a query to search
              </div>
            </div>
          ) : (
            <>
              <div
                className="table-row table-header"
                style={{ gridTemplateColumns: '50px 80px 100px 1fr' }}
              >
                <div>Rank</div>
                <div>Score</div>
                <div>PMID</div>
                <div>Title</div>
              </div>

              <div style={{ maxHeight: 500, overflowY: 'auto' }}>
                {results.map((r, i) => (
                  <div
                    key={r.id}
                    className="table-row"
                    style={{
                      gridTemplateColumns: '50px 80px 100px 1fr',
                      cursor: 'pointer',
                      background: selected?.id === r.id ? 'var(--bg-active)' : undefined,
                      borderLeft: selected?.id === r.id ? '3px solid var(--accent-green)' : '3px solid transparent',
                    }}
                    onClick={() => setSelected(r)}
                  >
                    <div style={{ 
                      fontWeight: 700, 
                      color: i === 0 ? 'var(--accent-green)' : 'var(--text-secondary)',
                      fontSize: 16
                    }}>
                      #{i + 1}
                    </div>
                    
                    <div style={{ 
                      fontFamily: 'var(--font-mono)', 
                      fontSize: 13,
                      color: getScoreColor(r.score),
                      fontWeight: 600
                    }}>
                      {r.score.toFixed(4)}
                    </div>
                    
                    <div style={{ 
                      fontFamily: 'var(--font-mono)', 
                      fontSize: 12,
                      color: 'var(--accent-blue)'
                    }}>
                      {r.payload?.pmid || r.id}
                    </div>
                    
                    <div style={{ 
                      overflow: 'hidden', 
                      textOverflow: 'ellipsis', 
                      whiteSpace: 'nowrap' 
                    }}>
                      {r.payload?.title || (
                        <span style={{ color: 'var(--text-muted)' }}>No title</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Detail Compare Panel */}
        {selected && (
          <div className="card" style={{ overflow: 'hidden' }}>
            <div className="card-header">
              <div className="card-title">🔬 Detail View</div>
              <button 
                className="btn-icon"
                onClick={() => setSelected(null)}
                title="Close"
              >
                ✕
              </button>
            </div>

            <div style={{ 
              display: 'flex', 
              flexDirection: 'column', 
              gap: 20,
              maxHeight: 500,
              overflowY: 'auto',
              padding: '0 4px'
            }}>
              {/* Score Section */}
              <div>
                <div className="section-label">SIMILARITY SCORE</div>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: 16,
                  background: 'var(--bg-tertiary)',
                  borderRadius: 8
                }}>
                  <div style={{
                    fontSize: 32,
                    fontWeight: 700,
                    fontFamily: 'var(--font-mono)',
                    color: getScoreColor(selected.score)
                  }}>
                    {selected.score.toFixed(4)}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{
                      height: 8,
                      background: 'var(--bg-secondary)',
                      borderRadius: 4,
                      overflow: 'hidden'
                    }}>
                      <div style={{
                        width: `${selected.score * 100}%`,
                        height: '100%',
                        background: `linear-gradient(90deg, var(--accent-blue), ${getScoreColor(selected.score)})`,
                        borderRadius: 4,
                        transition: 'width 0.3s ease'
                      }} />
                    </div>
                  </div>
                </div>
              </div>

              {/* Title */}
              {selected.payload?.title && (
                <div>
                  <div className="section-label">TITLE</div>
                  <div style={{
                    padding: 12,
                    background: 'var(--bg-tertiary)',
                    borderRadius: 8,
                    fontSize: 15,
                    fontWeight: 500,
                    lineHeight: 1.5
                  }}>
                    {selected.payload.title}
                  </div>
                </div>
              )}

              {/* Abstract */}
              {selected.payload?.abstract && (
                <div>
                  <div className="section-label">ABSTRACT</div>
                  <div className="text-box" style={{
                    maxHeight: 200,
                    overflowY: 'auto',
                    lineHeight: 1.7
                  }}>
                    {selected.payload.abstract}
                  </div>
                </div>
              )}

              {/* Vector Preview */}
              <div>
                <div className="section-label">VECTOR PREVIEW</div>
                <pre className="code-block" style={{ 
                  fontSize: 11, 
                  wordBreak: 'break-all',
                  whiteSpace: 'pre-wrap'
                }}>
                  {renderVectorPreview(selected.vector)}
                </pre>
              </div>

              {/* Full Payload */}
              <div>
                <div className="section-label">FULL PAYLOAD</div>
                <pre className="code-block" style={{ 
                  fontSize: 11, 
                  maxHeight: 200, 
                  overflowY: 'auto' 
                }}>
                  {JSON.stringify(selected.payload, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Help Section */}
      {results.length === 0 && !loading && (
        <div className="card" style={{ marginTop: 24 }}>
          <div className="card-header">
            <div className="card-title">💡 How to Use</div>
          </div>
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', 
            gap: 16 
          }}>
            <div style={{ 
              padding: 16, 
              background: 'var(--bg-tertiary)', 
              borderRadius: 8 
            }}>
              <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>1️⃣ Enter Query</div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                Type a natural language query like "mechanisms of CRISPR-Cas9 gene editing"
              </div>
            </div>
            <div style={{ 
              padding: 16, 
              background: 'var(--bg-tertiary)', 
              borderRadius: 8 
            }}>
              <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>2️⃣ Review Rankings</div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                Check similarity scores to verify semantic relevance of each result
              </div>
            </div>
            <div style={{ 
              padding: 16, 
              background: 'var(--bg-tertiary)', 
              borderRadius: 8 
            }}>
              <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>3️⃣ Compare Details</div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                Click any result to inspect abstract, payload, and vector data
              </div>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}

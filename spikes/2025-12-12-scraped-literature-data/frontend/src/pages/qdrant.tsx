/**
 * Qdrant Viewer - Vector Database Explorer
 *
 * Displays Qdrant collection info, vector list with search and pagination
 */

import { useEffect, useState } from 'react';
import Layout from '../components/Layout';

interface CollectionInfo {
  count: number;
  dimension: number;
  status: string;
}

interface VectorPayload {
  title?: string;
  abstract?: string;
  [key: string]: any;
}

interface VectorItem {
  id: string | number;
  payload?: VectorPayload;
}

export default function QdrantViewer() {
  const [info, setInfo] = useState<CollectionInfo | null>(null);
  const [vectors, setVectors] = useState<VectorItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [page, setPage] = useState(1);
  const [searchPmid, setSearchPmid] = useState('');

  const [expandedId, setExpandedId] = useState<string | number | null>(null);
  const [expandedVector, setExpandedVector] = useState<number[] | null>(null);
  const [expandingLoading, setExpandingLoading] = useState(false);

  const LIMIT = 10;

  /* -----------------------------------------
   * Fetch Collection Info
   * ---------------------------------------*/
  const fetchCollectionInfo = async () => {
    try {
      const res = await fetch('/api/qdrant/info');
      if (!res.ok) throw new Error('Failed to fetch collection info');
      const data = await res.json();
      setInfo(data);
    } catch (err) {
      console.error(err);
    }
  };

  /* -----------------------------------------
   * Fetch Vectors (Pagination + Search)
   * ---------------------------------------*/
  const fetchVectors = async () => {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({
        page: page.toString(),
        limit: LIMIT.toString(),
        ...(searchPmid && { pmid: searchPmid }),
      });

      const res = await fetch(`/api/qdrant/vectors?${params.toString()}`);
      if (!res.ok) throw new Error('Failed to fetch vectors');

      const data = await res.json();
      setVectors(Array.isArray(data) ? data : data.result || []);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  /* -----------------------------------------
   * Expand Vector Row (Fetch full vector)
   * ---------------------------------------*/
  const handleExpand = async (id: string | number) => {
    if (expandedId === id) {
      setExpandedId(null);
      setExpandedVector(null);
      return;
    }

    setExpandedId(id);
    setExpandingLoading(true);

    try {
      const res = await fetch(`/api/qdrant/vector/${id}`);
      if (res.ok) {
        const data = await res.json();
        setExpandedVector(data.vector || []);
      }
    } catch (err) {
      console.error('Failed to fetch vector detail', err);
    } finally {
      setExpandingLoading(false);
    }
  };

  const renderVectorPreview = (vec: number[]) => {
    if (!vec || vec.length === 0) return 'No vector data';
    const preview = vec.slice(0, 10).map(v => v.toFixed(4)).join(', ');
    return `[${preview}, ... total ${vec.length} dims]`;
  };

  /* -----------------------------------------
   * Effects
   * ---------------------------------------*/
  useEffect(() => {
    fetchCollectionInfo();
  }, []);

  useEffect(() => {
    fetchVectors();
  }, [page]);

  const handleSearch = () => {
    setPage(1);
    fetchVectors();
  };

  /* -----------------------------------------
   * Render
   * ---------------------------------------*/
  return (
    <Layout title="Qdrant Viewer" subtitle="Vector Database Explorer">
      {/* Error */}
      {error && (
        <div className="alert alert-error" style={{ marginBottom: 24 }}>
          ⚠️ {error}
        </div>
      )}

      {/* ===============================
          1️⃣ Stats Dashboard
         =============================== */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">TOTAL VECTORS</div>
          <div className="stat-value blue">
            {info?.count?.toLocaleString() ?? '-'}
          </div>
          <div className="stat-hint">Indexed points</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">DIMENSIONS</div>
          <div className="stat-value">
            {info?.dimension ?? '-'}
          </div>
          <div className="stat-hint">Embedding size</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">STATUS</div>
          <div className={`stat-value ${info?.status === 'green' ? 'green' : 'yellow'}`}>
            {info?.status ?? 'unknown'}
          </div>
          <div className="stat-hint">Cluster health</div>
        </div>
      </div>

      {/* ===============================
          2️⃣ Controls Bar
         =============================== */}
      <div
        className="card"
        style={{ marginBottom: 16 }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 16,
            flexWrap: 'wrap',
          }}
        >
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              className="input"
              placeholder="Search by PMID..."
              value={searchPmid}
              onChange={(e) => setSearchPmid(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              style={{ width: 220 }}
            />
            <button className="btn btn-secondary" onClick={handleSearch}>
              🔍 Search
            </button>
          </div>

          <div className="pagination">
            <button
              className="pagination-btn"
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
            >
              ← Prev
            </button>
            <span style={{ padding: '0 12px' }}>Page {page}</span>
            <button
              className="pagination-btn"
              onClick={() => setPage(p => p + 1)}
              disabled={vectors.length < LIMIT}
            >
              Next →
            </button>
          </div>
        </div>
      </div>

      {/* ===============================
          3️⃣ Vector List (Accordion)
         =============================== */}
      <div className="card">
        {loading ? (
          <div className="empty-state">⏳ Loading vectors...</div>
        ) : vectors.length === 0 ? (
          <div className="empty-state">
            📭 No vectors found
          </div>
        ) : (
          <>
            <div
              className="table-row table-header"
              style={{ gridTemplateColumns: '140px 1fr 80px' }}
            >
              <div>PMID</div>
              <div>Title</div>
              <div></div>
            </div>

            {vectors.map((vec) => (
              <div key={vec.id}>
                {/* Row */}
                <div
                  className="table-row"
                  style={{
                    gridTemplateColumns: '140px 1fr 80px',
                    cursor: 'pointer',
                  }}
                  onClick={() => handleExpand(vec.id)}
                >
                  <div
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: 12,
                      color: 'var(--accent-blue)',
                    }}
                  >
                    PMID: {vec.id}
                  </div>

                  <div>
                    {vec.payload?.title || (
                      <span style={{ color: 'var(--text-muted)' }}>
                        No title
                      </span>
                    )}
                  </div>

                  <div style={{ textAlign: 'right' }}>
                    {expandedId === vec.id ? '▲' : '▼'}
                  </div>
                </div>

                {/* Expanded */}
                {expandedId === vec.id && (
                  <div
                    style={{
                      padding: 20,
                      background: 'var(--bg-tertiary)',
                      borderBottom: '1px solid var(--border-primary)',
                    }}
                  >
                    {expandingLoading ? (
                      <div>Loading details...</div>
                    ) : (
                      <>
                        {/* Vector Preview */}
                        <div style={{ marginBottom: 16 }}>
                          <div className="section-label">
                            VECTOR PREVIEW (First 10 dims)
                          </div>
                          <pre className="code-block">
                            {expandedVector
                              ? renderVectorPreview(expandedVector)
                              : 'No vector data'}
                          </pre>
                        </div>

                        {/* Abstract */}
                        {vec.payload?.abstract && (
                          <div style={{ marginBottom: 16 }}>
                            <div className="section-label">ABSTRACT</div>
                            <div className="text-box">
                              {vec.payload.abstract}
                            </div>
                          </div>
                        )}

                        {/* Full Payload */}
                        <div>
                          <div className="section-label">FULL PAYLOAD</div>
                          <pre className="code-block">
                            {JSON.stringify(vec.payload, null, 2)}
                          </pre>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            ))}
          </>
        )}
      </div>
    </Layout>
  );
}

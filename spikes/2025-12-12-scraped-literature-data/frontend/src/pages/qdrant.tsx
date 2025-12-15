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
  /* ---------------- State ---------------- */
  const [info, setInfo] = useState<CollectionInfo | null>(null);
  const [vectors, setVectors] = useState<VectorItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Scroll 기반
  const [offset, setOffset] = useState<any>(null);
  const [hasNext, setHasNext] = useState(true);

  const [searchPmid, setSearchPmid] = useState('');

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [expandedVector, setExpandedVector] = useState<number[] | null>(null);
  const [expandingLoading, setExpandingLoading] = useState(false);

  const LIMIT = 10;

  /* ---------------- API Base ---------------- */
  const API_BASE = 'http://localhost:8000/api/admin/qdrant';


  /* -----------------------------------------
   * Fetch Collection Info
   * ---------------------------------------*/
  const fetchCollectionInfo = async () => {
    try {
      const res = await fetch(`${API_BASE}/info`);
      if (!res.ok) throw new Error('Failed to fetch collection info');
      setInfo(await res.json());
    } catch (e) {
      console.error(e);
    }
  };

  /* -----------------------------------------
   * Fetch Vectors (Pagination + Search)
   * ---------------------------------------*/
  const fetchVectors = async (reset = false) => {
    setLoading(true);
    setError(null);

   try {
      const res = await fetch(`${API_BASE}/scroll`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          limit: LIMIT,
          offset: reset ? null : offset,
          with_payload: true,
          with_vector: false,
        }),
      });

      if (!res.ok) throw new Error('Failed to scroll vectors');

      const data = await res.json();

      setVectors(reset ? data.points : [...vectors, ...data.points]);
      setOffset(data.next_offset);
      setHasNext(Boolean(data.next_offset));
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  /* -----------------------------------------
   * Expand Vector Row (Fetch full vector)
   * ---------------------------------------*/
  const handleExpand = async (id: string) => {
    if (expandedId === id) {
      setExpandedId(null);
      setExpandedVector(null);
      return;
    }

    setExpandedId(id);
    setExpandingLoading(true);

    try {
      const res = await fetch(`${API_BASE}/vector/${id}`);
      if (!res.ok) throw new Error('Failed to fetch vector');

      const data = await res.json();
      setExpandedVector(data.vector || []);
    } catch (e) {
      console.error(e);
    } finally {
      setExpandingLoading(false);
    }
  };

  const renderVectorPreview = (vec: number[]) => {
    if (!vec || vec.length === 0) return 'No vector data';
    return `[${vec.slice(0, 10).map(v => v.toFixed(4)).join(', ')}, ... total ${vec.length} dims]`;
  };

  /* -----------------------------------------
   * Effects
   * ---------------------------------------*/
  useEffect(() => {
    fetchCollectionInfo();
    fetchVectors(true);
  }, []);

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
          <div className="stat-value">{info?.dimension ?? '-'}</div>
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
      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>
            Scroll-based DB explorer (Qdrant native)
          </div>

          <button
            className="btn btn-ghost"
            disabled={!hasNext || loading}
            onClick={() => fetchVectors(false)}
          >
            {loading ? '⏳' : 'Load more'}
          </button>
        </div>
      </div>

      {/* ===============================
          3️⃣ Vector List (Accordion)
         =============================== */}
      <div className="card">
        {vectors.length === 0 && !loading ? (
          <div className="empty-state">📭 No vectors</div>
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
                <div
                  className="table-row"
                  style={{ gridTemplateColumns: '140px 1fr 80px', cursor: 'pointer' }}
                  onClick={() => handleExpand(vec.id)}
                >
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                    PMID: {vec.id}
                  </div>
                  <div>{vec.payload?.title || 'No title'}</div>
                  <div style={{ textAlign: 'right' }}>
                    {expandedId === vec.id ? '▲' : '▼'}
                  </div>
                </div>

                {expandedId === vec.id && (
                  <div style={{ padding: 20, background: 'var(--bg-tertiary)' }}>
                    {expandingLoading ? (
                      <div>Loading…</div>
                    ) : (
                      <>
                        <div className="section-label">
                          VECTOR PREVIEW
                        </div>
                        <pre className="code-block">
                          {expandedVector
                            ? renderVectorPreview(expandedVector)
                            : 'No vector'}
                        </pre>

                        {vec.payload?.abstract && (
                          <>
                            <div className="section-label">ABSTRACT</div>
                            <div className="text-box">{vec.payload.abstract}</div>
                          </>
                        )}

                        <div className="section-label">FULL PAYLOAD</div>
                        <pre className="code-block">
                          {JSON.stringify(vec.payload, null, 2)}
                        </pre>
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

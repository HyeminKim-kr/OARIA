/**
 * OARIA Literature - Paper Manager
 * 
 * 논문 목록 + 필터 + 삭제 관리
 */

import { useState, useEffect, useCallback } from 'react';
import Layout from '../../components/Layout';

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

interface Paper {
  pmid: string;
  title: string;
  abstract: string;
  authors: string[];
  journal: string;
  pubdate: string;
  embedding_status: string;
  created_at: string;
}

export default function PaperManager() {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('created_at');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');
  
  // Delete modal
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState('');
  const [deleting, setDeleting] = useState(false);

  const loadPapers = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        per_page: '20',
        sort,
        order,
        ...(search && { search }),
      });
      
      const res = await fetch(`${API_URL}/api/papers?${params}`);
      if (res.ok) {
        const data = await res.json();
        setPapers(data.papers);
        setTotalPages(data.total_pages);
        setTotal(data.total);
      }
    } catch (e) {
      console.error('Load error:', e);
    } finally {
      setLoading(false);
    }
  }, [page, search, sort, order]);

  useEffect(() => {
    loadPapers();
  }, [loadPapers]);

  const handleDeleteAll = async () => {
    if (deleteConfirm !== 'DELETE') return;
    
    setDeleting(true);
    try {
      const res = await fetch(`${API_URL}/api/papers/all`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirm: 'DELETE' }),
      });
      
      if (res.ok) {
        setShowDeleteModal(false);
        setDeleteConfirm('');
        loadPapers();
      }
    } catch (e) {
      console.error('Delete error:', e);
    } finally {
      setDeleting(false);
    }
  };

  const toggleSort = (field: string) => {
    if (sort === field) {
      setOrder(order === 'asc' ? 'desc' : 'asc');
    } else {
      setSort(field);
      setOrder('desc');
    }
    setPage(1);
  };

  return (
    <Layout title="Paper Manager" subtitle="논문 목록 관리">
      {/* Stats & Actions */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div style={{ fontSize: 14, color: 'var(--text-muted)' }}>
          Total: <strong style={{ color: 'var(--accent-green)' }}>{total.toLocaleString()}</strong> papers
        </div>
        <button
          onClick={() => setShowDeleteModal(true)}
          style={{
            padding: '10px 16px',
            borderRadius: 8,
            border: '1px solid #EF4444',
            background: 'transparent',
            color: '#EF4444',
            fontSize: 13,
            fontWeight: 500,
            cursor: 'pointer',
          }}
        >
          🗑️ Delete All
        </button>
      </div>

      {/* Search */}
      <div style={{ marginBottom: 24 }}>
        <input
          className="input"
          placeholder="Search by title, abstract, or PMID..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          style={{ width: '100%' }}
        />
      </div>

      {/* Table */}
      <div className="card" style={{ overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: 'var(--bg-tertiary)', fontSize: 12, textTransform: 'uppercase' }}>
              {[
                { key: 'pmid', label: 'PMID' },
                { key: 'title', label: 'Title' },
                { key: 'journal', label: 'Journal' },
                { key: 'pubdate', label: 'Date' },
                { key: 'embedding_status', label: 'Embed' },
              ].map((col) => (
                <th
                  key={col.key}
                  onClick={() => toggleSort(col.key)}
                  style={{
                    padding: 12,
                    textAlign: 'left',
                    cursor: 'pointer',
                    color: sort === col.key ? 'var(--accent-blue)' : 'var(--text-muted)',
                    fontWeight: 600,
                  }}
                >
                  {col.label} {sort === col.key && (order === 'asc' ? '↑' : '↓')}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
                  Loading...
                </td>
              </tr>
            ) : papers.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
                  No papers found
                </td>
              </tr>
            ) : papers.map((paper) => (
              <tr key={paper.pmid} style={{ borderTop: '1px solid var(--border-primary)' }}>
                <td style={{ padding: 12, fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--accent-blue)' }}>
                  {paper.pmid}
                </td>
                <td style={{ padding: 12, fontSize: 13, maxWidth: 400 }}>
                  <div style={{ 
                    overflow: 'hidden', 
                    textOverflow: 'ellipsis', 
                    whiteSpace: 'nowrap',
                    fontWeight: 500,
                  }}>
                    {paper.title}
                  </div>
                </td>
                <td style={{ padding: 12, fontSize: 12, color: 'var(--text-muted)', maxWidth: 150 }}>
                  <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {paper.journal}
                  </div>
                </td>
                <td style={{ padding: 12, fontSize: 12, color: 'var(--text-muted)' }}>
                  {paper.pubdate}
                </td>
                <td style={{ padding: 12 }}>
                  <span style={{
                    padding: '4px 8px',
                    borderRadius: 4,
                    fontSize: 11,
                    fontWeight: 500,
                    background: paper.embedding_status === 'done' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(245, 158, 11, 0.1)',
                    color: paper.embedding_status === 'done' ? '#10B981' : '#F59E0B',
                  }}>
                    {paper.embedding_status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 24 }}>
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            style={{
              padding: '8px 16px',
              borderRadius: 8,
              border: '1px solid var(--border-primary)',
              background: 'var(--bg-secondary)',
              color: page === 1 ? 'var(--text-muted)' : 'var(--text-primary)',
              cursor: page === 1 ? 'not-allowed' : 'pointer',
            }}
          >
            ← Prev
          </button>
          <span style={{ padding: '8px 16px', fontSize: 14, color: 'var(--text-muted)' }}>
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            style={{
              padding: '8px 16px',
              borderRadius: 8,
              border: '1px solid var(--border-primary)',
              background: 'var(--bg-secondary)',
              color: page === totalPages ? 'var(--text-muted)' : 'var(--text-primary)',
              cursor: page === totalPages ? 'not-allowed' : 'pointer',
            }}
          >
            Next →
          </button>
        </div>
      )}

      {/* Delete Modal */}
      {showDeleteModal && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0,0,0,0.6)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
        }}>
          <div style={{
            background: 'var(--bg-primary)',
            padding: 24,
            borderRadius: 16,
            width: 400,
            border: '1px solid var(--border-primary)',
          }}>
            <h3 style={{ marginBottom: 16, color: '#EF4444' }}>⚠️ Delete All Papers</h3>
            <p style={{ fontSize: 14, color: 'var(--text-muted)', marginBottom: 16 }}>
              이 작업은 모든 논문 <strong>{total.toLocaleString()}개</strong>를 삭제합니다.
              <br />계속하려면 <strong>DELETE</strong>를 입력하세요.
            </p>
            <input
              className="input"
              value={deleteConfirm}
              onChange={(e) => setDeleteConfirm(e.target.value)}
              placeholder="DELETE 입력"
              style={{ marginBottom: 16 }}
            />
            <div style={{ display: 'flex', gap: 12 }}>
              <button
                onClick={() => { setShowDeleteModal(false); setDeleteConfirm(''); }}
                style={{
                  flex: 1,
                  padding: 12,
                  borderRadius: 8,
                  border: '1px solid var(--border-primary)',
                  background: 'transparent',
                  color: 'var(--text-primary)',
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteAll}
                disabled={deleteConfirm !== 'DELETE' || deleting}
                style={{
                  flex: 1,
                  padding: 12,
                  borderRadius: 8,
                  border: 'none',
                  background: deleteConfirm === 'DELETE' ? '#EF4444' : 'var(--bg-tertiary)',
                  color: deleteConfirm === 'DELETE' ? '#fff' : 'var(--text-muted)',
                  cursor: deleteConfirm === 'DELETE' ? 'pointer' : 'not-allowed',
                  fontWeight: 600,
                }}
              >
                {deleting ? 'Deleting...' : 'Delete All'}
              </button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}

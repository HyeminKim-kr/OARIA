/**
 * OARIA DB Viewer — Enterprise Table Manager
 * 
 * Apple × Google × Notion 감성의 프리미엄 DB 관리 시스템
 * - 좌측: 테이블 목록
 * - 우측: 선택한 테이블의 실제 데이터
 */

import { useState, useEffect, useCallback } from 'react';
import Layout from '../../components/Layout';

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

interface TableInfo {
  name: string;
  count: number;
  description: string;
  latest_update: string | null;
  estimated_size_mb: number;
  registered: boolean;
}

interface TableRow {
  [key: string]: string | number | null;
}

export default function DBViewer() {
  // Tables (등록 + 미등록)
  const [registeredTables, setRegisteredTables] = useState<TableInfo[]>([]);
  const [unregisteredTables, setUnregisteredTables] = useState<TableInfo[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Selected Table
  const [selectedTable, setSelectedTable] = useState<string>('papers');
  const [rows, setRows] = useState<TableRow[]>([]);
  const [columns, setColumns] = useState<string[]>([]);
  const [rowsLoading, setRowsLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [perPage, setPerPage] = useState(30);
  
  // 삭제 모달 상태
  const [deleteModal, setDeleteModal] = useState<{
    open: boolean;
    type: 'single' | 'all';
    tableName: string;
    confirmText: string;
  }>({ open: false, type: 'single', tableName: '', confirmText: '' });
  const [deleting, setDeleting] = useState(false);

  // 테이블 목록 로드
  const loadTables = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/db/tables`);
      if (res.ok) {
        const data = await res.json();
        setRegisteredTables(data.registered_tables || []);
        setUnregisteredTables(data.unregistered_tables || []);
      }
    } catch (e) {
      console.error('Load tables error:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  // 테이블 데이터 로드
  const loadTableRows = useCallback(async () => {
    if (!selectedTable) return;
    
    setRowsLoading(true);
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        per_page: perPage.toString(),
        ...(search && { search }),
      });
      
      const res = await fetch(`${API_URL}/api/db/table/${selectedTable}/rows?${params}`);
      if (res.ok) {
        const data = await res.json();
        setRows(data.rows || []);
        setColumns(data.columns || []);
        setTotal(data.total || 0);
        setTotalPages(data.total_pages || 0);
      }
    } catch (e) {
      console.error('Load rows error:', e);
    } finally {
      setRowsLoading(false);
    }
  }, [selectedTable, page, search, perPage]);

  useEffect(() => {
    loadTables();
  }, [loadTables]);

  useEffect(() => {
    setPage(1);
    loadTableRows();
  }, [selectedTable]);

  useEffect(() => {
    setPage(1);
    loadTableRows();
  }, [selectedTable, perPage]);

  // 검색 디바운스
  useEffect(() => {
    const debounce = setTimeout(() => {
      setPage(1);
      loadTableRows();
    }, 500);
    return () => clearTimeout(debounce);
  }, [search]);

  const getSelectedTableInfo = () => [...registeredTables, ...unregisteredTables].find(t => t.name === selectedTable);
  
  // 전체 테이블
  const allTables = [...registeredTables, ...unregisteredTables];

  // 테이블 삭제 함수
  const handleDeleteTable = async (tableName: string) => {
    if (deleteModal.confirmText !== 'DELETE') {
      alert('확인을 위해 "DELETE"를 입력해주세요.');
      return;
    }
    
    setDeleting(true);
    try {
      const res = await fetch(`${API_URL}/api/db/table/${tableName}/full?confirm=DELETE`, {
        method: 'DELETE',
      });
      if (res.ok) {
        const data = await res.json();
        alert(`${tableName} 테이블에서 ${data.deleted}개 행이 삭제되었습니다.`);
        setDeleteModal({ open: false, type: 'single', tableName: '', confirmText: '' });
        loadTables();
        loadTableRows();
      } else {
        const err = await res.json();
        alert(`삭제 실패: ${err.detail}`);
      }
    } catch (e) {
      console.error('Delete error:', e);
      alert('삭제 중 오류가 발생했습니다.');
    } finally {
      setDeleting(false);
    }
  };

  // 전체 테이블 삭제 함수
  const handleDeleteAllTables = async () => {
    if (deleteModal.confirmText !== 'DELETE ALL') {
      alert('확인을 위해 "DELETE ALL"을 입력해주세요.');
      return;
    }
    
    setDeleting(true);
    try {
      for (const table of allTables) {
        await fetch(`${API_URL}/api/db/table/${table.name}/full?confirm=DELETE`, {
          method: 'DELETE',
        });
      }
      alert('모든 테이블이 삭제되었습니다.');
      setDeleteModal({ open: false, type: 'all', tableName: '', confirmText: '' });
      loadTables();
      loadTableRows();
    } catch (e) {
      console.error('Delete all error:', e);
      alert('삭제 중 오류가 발생했습니다.');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <Layout title="DB Viewer" subtitle="Enterprise Table Manager">
      <div style={{ display: 'flex', gap: 24, minHeight: 'calc(100vh - 300px)' }}>
        {/* 좌측: 테이블 목록 */}
        <div style={{
          width: 280,
          flexShrink: 0,
          background: 'var(--bg-secondary)',
          borderRadius: 12,
          border: '1px solid var(--border-primary)',
          overflow: 'hidden',
        }}>
          <div style={{
            padding: 16,
            borderBottom: '1px solid var(--border-primary)',
            fontSize: 13,
            fontWeight: 600,
            color: 'var(--text-muted)',
          }}>
            📁 TABLES
          </div>
          
          {loading ? (
            <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)' }}>
              Loading...
            </div>
          ) : (
            <div style={{ padding: 8, maxHeight: 'calc(100vh - 400px)', overflowY: 'auto' }}>
              {/* 등록된 테이블 */}
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 6, padding: '0 8px', fontWeight: 600 }}>
                  ✅ REGISTERED ({registeredTables.length})
                </div>
                {registeredTables.map((table) => (
                  <div
                    key={table.name}
                    onClick={() => setSelectedTable(table.name)}
                    style={{
                      padding: '12px 14px',
                      borderRadius: 8,
                      cursor: 'pointer',
                      background: selectedTable === table.name ? 'var(--accent-blue)' : 'transparent',
                      color: selectedTable === table.name ? '#fff' : 'var(--text-primary)',
                      marginBottom: 4,
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontWeight: 500 }}>🗂️ {table.name}</span>
                      <span style={{
                        fontSize: 11,
                        padding: '2px 8px',
                        borderRadius: 10,
                        background: selectedTable === table.name ? 'rgba(255,255,255,0.2)' : 'var(--bg-tertiary)',
                      }}>
                        {table.count.toLocaleString()}
                      </span>
                    </div>
                    <div style={{ fontSize: 11, marginTop: 4, opacity: 0.7 }}>
                      {table.description}
                    </div>
                  </div>
                ))}
              </div>
              
              {/* 미등록 테이블 */}
              {unregisteredTables.length > 0 && (
                <div>
                  <div style={{ fontSize: 10, color: 'var(--accent-yellow)', marginBottom: 6, padding: '0 8px', fontWeight: 600 }}>
                    ⚠️ UNREGISTERED ({unregisteredTables.length})
                  </div>
                  {unregisteredTables.map((table) => (
                    <div
                      key={table.name}
                      onClick={() => setSelectedTable(table.name)}
                      style={{
                        padding: '12px 14px',
                        borderRadius: 8,
                        cursor: 'pointer',
                        background: selectedTable === table.name ? 'rgba(245, 158, 11, 0.3)' : 'transparent',
                        color: selectedTable === table.name ? '#F59E0B' : 'var(--text-secondary)',
                        marginBottom: 4,
                        transition: 'all 0.15s ease',
                        border: '1px dashed var(--border-primary)',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontWeight: 500 }}>📋 {table.name}</span>
                        <span style={{
                          fontSize: 11,
                          padding: '2px 8px',
                          borderRadius: 10,
                          background: 'var(--bg-tertiary)',
                        }}>
                          {table.count.toLocaleString()}
                        </span>
                      </div>
                      <div style={{ fontSize: 11, marginTop: 4, opacity: 0.6 }}>
                        {table.description}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
          
          {/* 삭제 버튼들 */}
          <div style={{ padding: 8, borderTop: '1px solid var(--border-primary)' }}>
            <button
              onClick={() => setDeleteModal({ open: true, type: 'single', tableName: selectedTable, confirmText: '' })}
              style={{
                width: '100%',
                padding: '10px 12px',
                marginBottom: 8,
                borderRadius: 8,
                border: '1px solid rgba(239, 68, 68, 0.3)',
                background: 'rgba(239, 68, 68, 0.1)',
                color: '#EF4444',
                cursor: 'pointer',
                fontSize: 13,
                fontWeight: 500,
              }}
            >
              🗑️ {selectedTable} 삭제
            </button>
            <button
              onClick={() => setDeleteModal({ open: true, type: 'all', tableName: '', confirmText: '' })}
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: 8,
                border: '1px solid rgba(239, 68, 68, 0.5)',
                background: 'rgba(239, 68, 68, 0.2)',
                color: '#EF4444',
                cursor: 'pointer',
                fontSize: 13,
                fontWeight: 600,
              }}
            >
              ⚠️ 전체 DB 삭제
            </button>
          </div>
        </div>

        {/* 우측: 테이블 데이터 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <span style={{ fontSize: 20, fontWeight: 600 }}>
                📄 {selectedTable}
              </span>
              <span style={{ marginLeft: 12, fontSize: 13, color: 'var(--text-muted)' }}>
                {total.toLocaleString()} rows
              </span>
            </div>
            
            <div style={{ display: 'flex', gap: 12 }}>
              <input
                className="input"
                placeholder="🔍 Search..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ width: 200 }}
              />
              <button
                className="btn btn-ghost"
                onClick={loadTableRows}
              >
                🔄 Refresh
              </button>
              <select
                value={perPage}
                onChange={(e) => setPerPage(Number(e.target.value))}
                style={{
                  padding: '8px 12px',
                  borderRadius: 8,
                  border: '1px solid var(--border-primary)',
                  background: 'var(--bg-secondary)',
                  color: 'var(--text-primary)',
                  fontSize: 13,
                }}
              >
                <option value={30}>30개씩</option>
                <option value={50}>50개씩</option>
                <option value={100}>100개씩</option>
                <option value={200}>200개씩</option>
                <option value={10000}>전체 보기</option>
              </select>
            </div>
          </div>

          {/* Table */}
          <div className="card" style={{ flex: 1, overflow: 'hidden' }}>
            <div style={{ overflow: 'auto', maxHeight: 'calc(100vh - 450px)' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: 'var(--bg-tertiary)', position: 'sticky', top: 0 }}>
                    {columns.map((col) => (
                      <th key={col} style={{
                        padding: 12,
                        textAlign: 'left',
                        fontSize: 11,
                        fontWeight: 600,
                        color: 'var(--text-muted)',
                        textTransform: 'uppercase',
                        whiteSpace: 'nowrap',
                        borderBottom: '1px solid var(--border-primary)',
                      }}>
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rowsLoading ? (
                    <tr>
                      <td colSpan={columns.length} style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
                        Loading data...
                      </td>
                    </tr>
                  ) : rows.length === 0 ? (
                    <tr>
                      <td colSpan={columns.length} style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
                        No data
                      </td>
                    </tr>
                  ) : rows.map((row, idx) => (
                    <tr key={idx} style={{ borderBottom: '1px solid var(--border-primary)' }}>
                      {columns.map((col) => (
                        <td key={col} style={{
                          padding: 10,
                          fontSize: 12,
                          maxWidth: 250,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}>
                          {/* KST 시간 필드 우선 표시 */}
                          {col.endsWith('_at') && row[`${col}_kst`]
                            ? row[`${col}_kst`]
                            : row[col] ?? '-'}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div style={{ display: 'flex', justifyContent: 'center', gap: 8 }}>
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                style={{
                  padding: '8px 16px',
                  borderRadius: 6,
                  border: '1px solid var(--border-primary)',
                  background: 'var(--bg-secondary)',
                  color: page === 1 ? 'var(--text-muted)' : 'var(--text-primary)',
                  cursor: page === 1 ? 'not-allowed' : 'pointer',
                }}
              >
                ← Prev
              </button>
              <span style={{ padding: '8px 16px', fontSize: 13, color: 'var(--text-muted)' }}>
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                style={{
                  padding: '8px 16px',
                  borderRadius: 6,
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
        </div>
      </div>
      
      {/* 삭제 확인 모달 */}
      {deleteModal.open && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.7)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
        }}>
          <div style={{
            background: 'var(--bg-primary)',
            borderRadius: 16,
            padding: 24,
            width: 400,
            border: '1px solid var(--border-primary)',
          }}>
            <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 16, color: '#EF4444' }}>
              ⚠️ {deleteModal.type === 'all' ? '전체 DB 삭제' : `${deleteModal.tableName} 테이블 삭제`}
            </div>
            <div style={{ marginBottom: 16, color: 'var(--text-muted)', fontSize: 14, lineHeight: 1.6 }}>
              {deleteModal.type === 'all' ? (
                <>모든 테이블의 데이터가 삭제됩니다. 이 작업은 <strong style={{ color: '#EF4444' }}>되돌릴 수 없습니다</strong>. 확인하려면 아래에 <strong>"DELETE ALL"</strong>을 입력하세요.</>
              ) : (
                <><strong>{deleteModal.tableName}</strong> 테이블의 모든 데이터가 삭제됩니다. 확인하려면 아래에 <strong>"DELETE"</strong>를 입력하세요.</>
              )}
            </div>
            <input
              type="text"
              className="input"
              placeholder={deleteModal.type === 'all' ? 'DELETE ALL' : 'DELETE'}
              value={deleteModal.confirmText}
              onChange={(e) => setDeleteModal(prev => ({ ...prev, confirmText: e.target.value }))}
              style={{ width: '100%', marginBottom: 16 }}
            />
            <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
              <button
                className="btn btn-ghost"
                onClick={() => setDeleteModal({ open: false, type: 'single', tableName: '', confirmText: '' })}
                disabled={deleting}
              >
                취소
              </button>
              <button
                onClick={() => deleteModal.type === 'all' ? handleDeleteAllTables() : handleDeleteTable(deleteModal.tableName)}
                disabled={deleting || (deleteModal.type === 'all' ? deleteModal.confirmText !== 'DELETE ALL' : deleteModal.confirmText !== 'DELETE')}
                style={{
                  padding: '10px 20px',
                  borderRadius: 8,
                  border: 'none',
                  background: (deleteModal.type === 'all' ? deleteModal.confirmText === 'DELETE ALL' : deleteModal.confirmText === 'DELETE') 
                    ? '#EF4444' : 'var(--bg-tertiary)',
                  color: '#fff',
                  cursor: 'pointer',
                  fontWeight: 600,
                  opacity: deleting ? 0.5 : 1,
                }}
              >
                {deleting ? '삭제 중...' : '삭제'}
              </button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}

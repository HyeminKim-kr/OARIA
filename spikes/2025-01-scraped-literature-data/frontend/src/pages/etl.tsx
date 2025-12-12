/**
 * OARIA Enterprise — ETL Control Panel v3
 * 
 * Apple × Google × Notion 감성
 * - Search with Progress %
 * - Manual Run (Resume from last index)
 * - Auto Mode with Pause/Cancel
 * - Global Console integration
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import Layout from '../components/Layout';

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

interface SearchStats {
  term: string;
  pubmed_total: number;
  fetched: number;
  remaining: number;
  progress: number;
  resume_index: number;
  last_pmid: string | null;
  last_sync_kst: string | null;
  total_runs: number;
  total_inserted: number;
  total_skipped: number;
  eta_minutes: number | null;
  eta_display: string | null;
}

interface ETLStatus {
  job_id: string;
  status: 'idle' | 'running' | 'completed' | 'error' | 'stopped';
  progress: number;
  inserted: number;
  skipped: number;
  message: string;
}

interface AutoETLStatus {
  running: boolean;
  paused: boolean;
  term: string;
  batch_size: number;
  current_job_id: string | null;
  current_offset: number;
  total_batches: number;
  completed_batches: number;
}

export default function ETLControlPanel() {
  // Search
  const [term, setTerm] = useState('breast cancer');
  const [stats, setStats] = useState<SearchStats | null>(null);
  const [searching, setSearching] = useState(false);
  
  // Options
  const [showOptions, setShowOptions] = useState(false);
  const [batchSize, setBatchSize] = useState(100);
  
  // ETL Status
  const [etlStatus, setEtlStatus] = useState<ETLStatus | null>(null);
  const [manualLoading, setManualLoading] = useState(false);
  
  // Auto ETL
  const [autoStatus, setAutoStatus] = useState<AutoETLStatus | null>(null);
  
  // ETL Logs (for both Manual and Auto)
  const [etlLogs, setEtlLogs] = useState<string[]>([]);
  
  // Realtime
  const [realtimeEnabled, setRealtimeEnabled] = useState(false);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const autoIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const addEtlLog = useCallback((message: string) => {
    const timestamp = new Date().toLocaleTimeString('ko-KR', { hour12: false });
    setEtlLogs((prev: string[]) => [...prev.slice(-10), `[${timestamp}] ${message}`]);
  }, []);

  // Update stats without full refresh (only updates fetched, resume_index, ETA, last_sync)
  const updateStatsPartial = useCallback(async () => {
    if (!term.trim()) return;
    try {
      const res = await fetch(`${API_URL}/api/etl/search?term=${encodeURIComponent(term)}`);
      if (res.ok) {
        const newStats = await res.json();
        setStats((prev: SearchStats | null) => prev ? {
          ...prev,
          fetched: newStats.fetched,
          remaining: newStats.remaining,
          progress: newStats.progress,
          resume_index: newStats.resume_index,
          eta_minutes: newStats.eta_minutes,
          eta_display: newStats.eta_display,
          last_sync_kst: newStats.last_sync_kst,
        } : newStats);
      }
    } catch (e) {
      console.error('Partial stats update error:', e);
    }
  }, [term]);

  // Search 실행 (full refresh)
  const handleSearch = useCallback(async () => {
    if (!term.trim()) return;
    
    setSearching(true);
    try {
      const res = await fetch(`${API_URL}/api/etl/search?term=${encodeURIComponent(term)}`);
      if (res.ok) {
        setStats(await res.json());
      }
    } catch (e) {
      console.error('Search error:', e);
    } finally {
      setSearching(false);
    }
  }, [term]);

  // 디바운스 검색
  useEffect(() => {
    const debounce = setTimeout(handleSearch, 600);
    return () => clearTimeout(debounce);
  }, [term, handleSearch]);

  // Auto/Realtime 상태 폴링
  useEffect(() => {
    const poll = async () => {
      try {
        const [autoRes, realtimeRes] = await Promise.all([
          fetch(`${API_URL}/api/etl/auto/status`),
          fetch(`${API_URL}/api/etl/realtime/status`),
        ]);
        if (autoRes.ok) setAutoStatus(await autoRes.json());
        if (realtimeRes.ok) {
          const data = await realtimeRes.json();
          setRealtimeEnabled(data.enabled);
        }
      } catch (e) {}
    };
    
    poll();
    const interval = setInterval(poll, 3000);
    return () => clearInterval(interval);
  }, []);

  // Manual Run (Resume from last index)
  const handleManualRun = async () => {
    setManualLoading(true);
    try {
      const offset = stats?.resume_index || 0;
      
      const res = await fetch(`${API_URL}/api/etl/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ term, limit: batchSize, offset }),
      });
      
      if (res.ok) {
        const data = await res.json();
        setEtlStatus({
          job_id: data.job_id,
          status: 'running',
          progress: 0,
          inserted: 0,
          skipped: 0,
          message: `Resuming from index ${offset}...`,
        });
        pollETLStatus(data.job_id);
      }
    } catch (e) {
      console.error('Manual run error:', e);
    } finally {
      setManualLoading(false);
    }
  };

  // ETL 상태 폴링 (Manual Run용)
  const pollETLStatus = (jobId: string) => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    
    intervalRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_URL}/api/etl/status?job_id=${jobId}`);
        if (res.ok) {
          const data = await res.json();
          setEtlStatus(data);
          
          if (['completed', 'error', 'stopped'].includes(data.status)) {
            clearInterval(intervalRef.current!);
            // Update stats partially (fetched, resume_index, ETA, last_sync)
            await updateStatsPartial();
            // Add completion log
            addEtlLog(`✅ Completed == Inserted: +${data.inserted} | Skipped: ${data.skipped}`);
          }
        }
      } catch (e) {
        clearInterval(intervalRef.current!);
      }
    }, 1000);
  };

  // Auto ETL Job Polling (for batch completions)
  const lastCompletedBatchRef = useRef<number>(0);
  
  const startAutoPolling = useCallback(() => {
    if (autoIntervalRef.current) clearInterval(autoIntervalRef.current);
    lastCompletedBatchRef.current = 0;
    
    autoIntervalRef.current = setInterval(async () => {
      try {
        // Check auto status
        const autoRes = await fetch(`${API_URL}/api/etl/auto/status`);
        if (autoRes.ok) {
          const auto = await autoRes.json();
          setAutoStatus(auto);
          
          // If there's a current job, check its status for UI progress
          if (auto.current_job_id && auto.running && !auto.paused) {
            const jobRes = await fetch(`${API_URL}/api/etl/status?job_id=${auto.current_job_id}`);
            if (jobRes.ok) {
              const job = await jobRes.json();
              setEtlStatus(job);
            }
          }
          
          // Check if new batch completed (compare with tracked count)
          if (auto.completed_batches > lastCompletedBatchRef.current) {
            lastCompletedBatchRef.current = auto.completed_batches;
            // Update stats when batch completes
            await updateStatsPartial();
          }
          
          // Stop polling if auto ETL is no longer running
          if (!auto.running) {
            clearInterval(autoIntervalRef.current!);
            autoIntervalRef.current = null;
            addEtlLog(`🏁 Auto ETL Ended (Completed ${auto.completed_batches} batches)`);
          }
        }
      } catch (e) {
        console.error('Auto polling error:', e);
      }
    }, 1500);
  }, [updateStatsPartial, addEtlLog]);

  // Auto ETL 제어
  const handleAutoStart = async () => {
    const offset = stats?.resume_index || 0;
    const res = await fetch(`${API_URL}/api/etl/auto/start?term=${encodeURIComponent(term)}&batch_size=${batchSize}`, {
      method: 'POST',
    });
    if (res.ok) {
      addEtlLog(`🟢 Auto ETL Started (term="${term}", batch=${batchSize})`);
      startAutoPolling();
    }
  };

  const handleAutoPause = async () => {
    const res = await fetch(`${API_URL}/api/etl/auto/pause`, { method: 'POST' });
    if (res.ok) {
      addEtlLog(`🔴 Auto ETL Paused`);
    }
  };

  const handleAutoResume = async () => {
    const res = await fetch(`${API_URL}/api/etl/auto/resume`, { method: 'POST' });
    if (res.ok) {
      addEtlLog(`🟡 Auto ETL Resumed`);
      startAutoPolling();
    }
  };

  const handleAutoCancel = async () => {
    const res = await fetch(`${API_URL}/api/etl/auto/cancel`, { method: 'POST' });
    if (res.ok) {
      addEtlLog(`⏹️ Auto ETL Cancelled`);
      if (autoIntervalRef.current) {
        clearInterval(autoIntervalRef.current);
        autoIntervalRef.current = null;
      }
    }
  };

  // Realtime Toggle
  const toggleRealtime = async () => {
    if (realtimeEnabled) {
      await fetch(`${API_URL}/api/etl/realtime/stop`, { method: 'POST' });
    } else {
      await fetch(`${API_URL}/api/etl/realtime/start?term=${encodeURIComponent(term)}&interval_seconds=60`, {
        method: 'POST',
      });
    }
  };

  const isAutoRunning = autoStatus?.running && !autoStatus?.paused;
  const isAutoPaused = autoStatus?.running && autoStatus?.paused;

  return (
    <Layout title="ETL Control Panel" subtitle="Search-Based ETL with Resume & Progress">
      <div style={{ 
        maxWidth: 750, 
        margin: '0 auto',
        minWidth: 650,
      }}>
        
        {/* Search Section */}
        <div className="card" style={{ marginBottom: 24, padding: 24 }}>
          {/* Search Input */}
          <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
            <div style={{ flex: 1, position: 'relative' }}>
              <input
                className="input"
                value={term}
                onChange={(e) => setTerm(e.target.value)}
                placeholder="Enter search term..."
                style={{ 
                  width: '100%',
                  fontSize: 18, 
                  padding: '16px 20px',
                  fontWeight: 500,
                }}
              />
            </div>
            <button
              className="btn btn-ghost"
              onClick={() => setShowOptions(!showOptions)}
              style={{ padding: '16px 20px' }}
            >
              ⚙️ {showOptions ? '▲' : '▼'}
            </button>
          </div>

          {/* Progress Bar & Stats (with loading state) */}
          <div style={{ 
            minHeight: 80, 
            display: 'flex', 
            flexDirection: 'column',
            justifyContent: 'center',
          }}>
            {searching ? (
              <div style={{ 
                textAlign: 'center', 
                padding: 40,
                color: 'var(--text-muted)',
              }}>
                <div style={{ fontSize: 24, marginBottom: 12 }}>⏳</div>
                <div>Searching PubMed...</div>
              </div>
            ) : stats ? (
              <>
                <div style={{ marginBottom: 20 }}>
                  <div style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    marginBottom: 8,
                    fontSize: 14,
                  }}>
                    <span style={{ fontWeight: 600, color: 'var(--accent-blue)' }}>
                      Progress: {stats.progress}%
                    </span>
                    <span style={{ color: 'var(--text-muted)' }}>
                      Fetched: <strong>{stats.fetched.toLocaleString()}</strong> / {stats.pubmed_total.toLocaleString()}
                    </span>
                  </div>
                  
                  <div style={{
                    height: 8,
                    background: 'var(--bg-tertiary)',
                    borderRadius: 4,
                    overflow: 'hidden',
                  }}>
                    <div style={{
                      width: `${stats.progress}%`,
                      height: '100%',
                      background: 'linear-gradient(90deg, #3B82F6, #10B981)',
                      borderRadius: 4,
                      transition: 'width 0.5s ease',
                    }} />
                  </div>
                </div>
              </>
            ) : (
              <div style={{ 
                textAlign: 'center', 
                padding: 40,
                color: 'var(--text-muted)',
              }}>
                Enter a search term to see statistics
              </div>
            )}
          </div>

          {/* Stats Grid */}
          {stats && (
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: 16,
              padding: 16,
              background: 'var(--bg-tertiary)',
              borderRadius: 12,
            }}>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>REMAINING</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--accent-orange)', fontFamily: 'var(--font-mono)' }}>
                  {stats.remaining.toLocaleString()}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>RESUME INDEX</div>
                <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
                  #{stats.resume_index.toLocaleString()}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>ETA</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)' }}>
                  {stats.eta_display || '-'}
                </div>
              </div>
            </div>
          )}

          {/* Last Sync */}
          {stats?.last_sync_kst && (
            <div style={{ 
              marginTop: 16, 
              fontSize: 12, 
              color: 'var(--text-muted)',
              textAlign: 'center',
            }}>
              Last Sync: <strong>{stats.last_sync_kst}</strong>
            </div>
          )}
        </div>

        {/* ETL Execution Controls */}
        <div className="card" style={{ marginBottom: 24, padding: 24 }}>
          <div style={{ 
            fontSize: 14, 
            fontWeight: 600, 
            marginBottom: 20,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}>
            <span>▶️</span>
            ETL Execution Controls
            {autoStatus?.running && (
              <span style={{
                marginLeft: 'auto',
                padding: '4px 12px',
                borderRadius: 20,
                fontSize: 11,
                fontWeight: 600,
                background: isAutoPaused ? 'rgba(239, 68, 68, 0.1)' : 'rgba(245, 158, 11, 0.1)',
                color: isAutoPaused ? '#EF4444' : '#F59E0B',
              }}>
                {isAutoPaused ? '🔴 PAUSED' : '🟡 AUTO RUNNING'}
              </span>
            )}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {/* Manual Run */}
            <button
              onClick={handleManualRun}
              disabled={manualLoading || !term.trim() || isAutoRunning}
              style={{
                padding: '14px 24px',
                borderRadius: 10,
                border: 'none',
                background: manualLoading ? 'var(--bg-tertiary)' : 'var(--accent-blue)',
                color: '#fff',
                fontSize: 14,
                fontWeight: 600,
                cursor: manualLoading || isAutoRunning ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
                opacity: isAutoRunning ? 0.5 : 1,
              }}
            >
              {manualLoading ? '⏳ Running...' : `▶ Manual Run (Resume from #${stats?.resume_index || 0}, batch=${batchSize})`}
            </button>

            {/* ETL Status */}
            {etlStatus && etlStatus.status === 'running' && (
              <div style={{
                padding: 12,
                background: 'rgba(59, 130, 246, 0.1)',
                borderRadius: 8,
                fontSize: 13,
              }}>
                <span style={{ color: '#3B82F6', fontWeight: 500 }}>⏳ {etlStatus.message}</span>
                {etlStatus.inserted > 0 && (
                  <span style={{ marginLeft: 12 }}>
                    Inserted: <strong style={{ color: 'var(--accent-green)' }}>+{etlStatus.inserted}</strong>
                  </span>
                )}
              </div>
            )}

            {etlStatus && etlStatus.status === 'completed' && (
              <div style={{
                padding: 12,
                background: 'rgba(16, 185, 129, 0.1)',
                borderRadius: 8,
                fontSize: 13,
                color: '#10B981',
              }}>
                ✅ Completed — Inserted: <strong>+{etlStatus.inserted}</strong> | Skipped: <strong>{etlStatus.skipped}</strong>
              </div>
            )}

            {/* Auto Mode Buttons */}
            <div style={{ display: 'flex', gap: 12 }}>
              {!autoStatus?.running ? (
                <button
                  onClick={handleAutoStart}
                  disabled={!term.trim()}
                  style={{
                    flex: 1,
                    padding: '12px 20px',
                    borderRadius: 10,
                    border: '2px solid #10B981',
                    background: 'transparent',
                    color: '#10B981',
                    fontSize: 14,
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  🟢 Auto Start
                </button>
              ) : (
                <>
                  {isAutoPaused ? (
                    <button
                      onClick={handleAutoResume}
                      style={{
                        flex: 1,
                        padding: '12px 20px',
                        borderRadius: 10,
                        border: '2px solid #F59E0B',
                        background: '#F59E0B',
                        color: '#fff',
                        fontSize: 14,
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      🟡 Resume
                    </button>
                  ) : (
                    <button
                      onClick={handleAutoPause}
                      style={{
                        flex: 1,
                        padding: '12px 20px',
                        borderRadius: 10,
                        border: '2px solid #F59E0B',
                        background: 'transparent',
                        color: '#F59E0B',
                        fontSize: 14,
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      ⏸️ Pause
                    </button>
                  )}
                  <button
                    onClick={handleAutoCancel}
                    style={{
                      flex: 1,
                      padding: '12px 20px',
                      borderRadius: 10,
                      border: '2px solid #EF4444',
                      background: 'transparent',
                      color: '#EF4444',
                      fontSize: 14,
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    ⏹️ Cancel
                  </button>
                </>
              )}
            </div>

            {/* ETL Logs (for both Manual and Auto) */}
            {etlLogs.length > 0 && (
              <div style={{
                marginTop: 16,
                padding: 12,
                background: 'var(--bg-tertiary)',
                borderRadius: 8,
                fontSize: 12,
                fontFamily: 'var(--font-mono)',
                maxHeight: 150,
                overflow: 'auto',
              }}>
                {etlLogs.map((log: string, idx: number) => (
                  <div key={idx} style={{ 
                    padding: '4px 0',
                    borderBottom: idx < etlLogs.length - 1 ? '1px solid var(--border-primary)' : 'none',
                  }}>
                    {log}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Options Panel */}
        {showOptions && (
          <div className="card" style={{ marginBottom: 24, padding: 24 }}>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>⚙️ Advanced Options</div>
            
            {/* Batch Size */}
            <div style={{ marginBottom: 20 }}>
              <label style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8, display: 'block' }}>
                Batch Size
              </label>
              <div style={{ display: 'flex', gap: 8 }}>
                {[50, 100, 200, 500].map((size) => (
                  <button
                    key={size}
                    onClick={() => setBatchSize(size)}
                    style={{
                      padding: '10px 20px',
                      borderRadius: 8,
                      border: 'none',
                      background: batchSize === size ? 'var(--accent-blue)' : 'var(--bg-tertiary)',
                      color: batchSize === size ? '#fff' : 'var(--text-primary)',
                      fontSize: 14,
                      fontWeight: 500,
                      cursor: 'pointer',
                    }}
                  >
                    {size}
                  </button>
                ))}
              </div>
            </div>

            {/* Realtime Pull */}
            <div style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center',
              padding: 16,
              background: 'var(--bg-tertiary)',
              borderRadius: 10,
            }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 500 }}>Real-time Pull (1 min)</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                  Automatically fetch new papers every minute
                </div>
              </div>
              <button
                onClick={toggleRealtime}
                style={{
                  padding: '10px 24px',
                  borderRadius: 20,
                  border: 'none',
                  background: realtimeEnabled ? 'var(--accent-green)' : 'var(--bg-secondary)',
                  color: realtimeEnabled ? '#fff' : 'var(--text-muted)',
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                {realtimeEnabled ? 'ON' : 'OFF'}
              </button>
            </div>
          </div>
        )}

        {/* Quick Examples */}
        <div style={{ 
          textAlign: 'center',
          fontSize: 12, 
          color: 'var(--text-muted)',
        }}>
          Examples:{' '}
          {['breast cancer', 'BRCA1', 'immunotherapy', 'COVID-19'].map((ex) => (
            <button
              key={ex}
              onClick={() => setTerm(ex)}
              style={{
                marginLeft: 8,
                padding: '6px 12px',
                borderRadius: 6,
                border: 'none',
                background: term === ex ? 'var(--accent-blue)' : 'var(--bg-tertiary)',
                color: term === ex ? '#fff' : 'var(--text-primary)',
                fontSize: 11,
                cursor: 'pointer',
              }}
            >
              {ex}
            </button>
          ))}
        </div>
      </div>
    </Layout>
  );
}

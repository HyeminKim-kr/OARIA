/**
 * OARIA Literature - Resizable Console Component
 * 
 * Flex layout 내 자연스럽게 배치되는 리사이즈 가능한 콘솔
 * SSE 로그 스트리밍 + Virtual Scrolling 지원
 */

import { useState, useEffect, useRef, useCallback } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

interface LogEntry {
  timestamp: string;
  level: 'info' | 'success' | 'warning' | 'error';
  message: string;
}

interface ResizableConsoleProps {
  isOpen: boolean;
  onToggle: () => void;
  jobId?: string | null;
  minHeight?: number;
  maxHeight?: number;
  defaultHeight?: number;
}

export default function ResizableConsole({
  isOpen,
  onToggle,
  jobId,
  minHeight = 150,
  maxHeight = 600,
  defaultHeight = 280,
}: ResizableConsoleProps) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [height, setHeight] = useState(defaultHeight);
  const [isResizing, setIsResizing] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const logContainerRef = useRef<HTMLDivElement>(null);
  const startY = useRef(0);
  const startHeight = useRef(0);

  // SSE 로그 스트리밍
  useEffect(() => {
    if (!isOpen || !jobId) return;

    const eventSource = new EventSource(`${API_URL}/api/etl/logs?job_id=${jobId}`);
    
    eventSource.addEventListener('log', (e) => {
      try {
        const log = JSON.parse(e.data);
        setLogs(prev => {
          const newLogs = [...prev, log];
          // 최대 1000개 로그 유지 (메모리 관리)
          return newLogs.slice(-1000);
        });
      } catch (err) {
        console.error('Log parse error:', err);
      }
    });

    eventSource.onerror = () => {
      eventSource.close();
    };

    return () => eventSource.close();
  }, [isOpen, jobId]);

  // Fallback: polling (SSE 미지원 시)
  useEffect(() => {
    if (!isOpen) return;
    
    const fetchLogs = async () => {
      try {
        const res = await fetch(`${API_URL}/api/logs?limit=100`);
        if (res.ok) {
          const data = await res.json();
          setLogs(data.logs || []);
        }
      } catch (e) {
        // Silent error
      }
    };

    fetchLogs();
    const interval = setInterval(fetchLogs, 2000);
    return () => clearInterval(interval);
  }, [isOpen]);

  // Auto-scroll
  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  // Resize handlers
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    startY.current = e.clientY;
    startHeight.current = height;
  }, [height]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing) return;
      const delta = startY.current - e.clientY;
      const newHeight = Math.min(Math.max(startHeight.current + delta, minHeight), maxHeight);
      setHeight(newHeight);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'ns-resize';
      document.body.style.userSelect = 'none';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizing, minHeight, maxHeight]);

  const clearLogs = async () => {
    try {
      await fetch(`${API_URL}/api/logs/clear`, { method: 'POST' });
      setLogs([]);
    } catch (e) {
      console.error('Clear logs error:', e);
    }
  };

  const getLevelStyle = (level: string) => {
    switch (level) {
      case 'success': return { color: '#34D399', icon: '✅' };
      case 'warning': return { color: '#FBBF24', icon: '⚠️' };
      case 'error': return { color: '#F87171', icon: '❌' };
      default: return { color: '#60A5FA', icon: 'ℹ️' };
    }
  };

  const formatTime = (timestamp: string) => {
    try {
      return new Date(timestamp).toLocaleTimeString('en-US', { 
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false 
      });
    } catch { return timestamp; }
  };

  return (
    <div 
      className="console-container"
      style={{
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--bg-secondary)',
        borderTop: '1px solid var(--border-primary)',
        transition: isResizing ? 'none' : 'height 0.2s ease',
      }}
    >
      {/* Resize Handle (드래그 영역) */}
      {isOpen && (
        <div
          onMouseDown={handleMouseDown}
          style={{
            height: 8,
            background: isResizing ? 'var(--accent-green)' : 'var(--bg-tertiary)',
            cursor: 'ns-resize',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'background 0.15s ease',
          }}
          onMouseEnter={(e) => e.currentTarget.style.background = 'var(--accent-green)'}
          onMouseLeave={(e) => !isResizing && (e.currentTarget.style.background = 'var(--bg-tertiary)')}
        >
          <div style={{
            width: 40,
            height: 4,
            borderRadius: 2,
            background: 'var(--text-muted)',
            opacity: 0.5,
          }} />
        </div>
      )}

      {/* Toggle Header */}
      <div
        onClick={onToggle}
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '10px 20px',
          background: 'var(--bg-secondary)',
          cursor: 'pointer',
          fontSize: 13,
          fontWeight: 500,
          color: 'var(--text-secondary)',
          borderBottom: isOpen ? '1px solid var(--border-primary)' : 'none',
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span>🖥️</span> Console
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {logs.length > 0 && (
            <span style={{
              background: 'var(--accent-green)',
              color: '#0D1117',
              fontSize: 11,
              fontWeight: 600,
              padding: '2px 8px',
              borderRadius: 10,
            }}>
              {logs.length}
            </span>
          )}
          <span style={{ fontSize: 12 }}>{isOpen ? '▼' : '▲'}</span>
        </span>
      </div>

      {/* Console Content */}
      {isOpen && (
        <div style={{ height, display: 'flex', flexDirection: 'column', background: '#0A0C10' }}>
          {/* Toolbar */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '8px 16px',
            background: '#0D0F14',
            borderBottom: '1px solid #1C2128',
            fontSize: 12,
          }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-muted)', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
                style={{ accentColor: 'var(--accent-green)' }}
              />
              Auto-scroll
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
              <button 
                onClick={(e) => { e.stopPropagation(); setLogs(prev => [...prev]); }}
                className="console-btn"
              >
                🔄 Refresh
              </button>
              <button onClick={(e) => { e.stopPropagation(); clearLogs(); }} className="console-btn">
                🗑️ Clear
              </button>
            </div>
          </div>

          {/* Log Viewer */}
          <div 
            ref={logContainerRef}
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: '12px 16px',
              fontFamily: 'var(--font-mono)',
              fontSize: 12,
            }}
          >
            {logs.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: 40 }}>
                Waiting for logs... Start an ETL job to see activity.
              </div>
            ) : (
              logs.map((log, idx) => {
                const style = getLevelStyle(log.level);
                return (
                  <div 
                    key={idx} 
                    style={{
                      display: 'flex',
                      gap: 12,
                      padding: '3px 0',
                      borderBottom: '1px solid rgba(48, 54, 61, 0.3)',
                    }}
                  >
                    <span style={{ color: '#6E7681', flexShrink: 0, fontSize: 11 }}>
                      {formatTime(log.timestamp)}
                    </span>
                    <span style={{ flexShrink: 0 }}>{style.icon}</span>
                    <span style={{ color: style.color }}>{log.message}</span>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      <style jsx>{`
        .console-btn {
          background: transparent;
          border: 1px solid #30363D;
          color: var(--text-muted);
          padding: 4px 12px;
          border-radius: 4px;
          cursor: pointer;
          transition: all 0.15s ease;
        }
        .console-btn:hover {
          background: #21262D;
          border-color: #484F58;
        }
      `}</style>
    </div>
  );
}

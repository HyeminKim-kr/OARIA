/**
 * OARIA Literature - Console Panel
 * 
 * 실시간 로그 표시 (리사이즈 가능)
 */

import { useState, useEffect, useRef } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
}

export default function Console() {
  const [isOpen, setIsOpen] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const [height, setHeight] = useState(280);
  const [isResizing, setIsResizing] = useState(false);
  const logContainerRef = useRef<HTMLDivElement>(null);
  const startY = useRef(0);
  const startHeight = useRef(0);

  const fetchLogs = async () => {
    try {
      const res = await fetch(`${API_URL}/api/logs?limit=100`);
      if (res.ok) setLogs((await res.json()).logs || []);
    } catch (e) {
      // Silent error - console polling
    }
  };

  useEffect(() => {
    if (!isOpen) return;
    fetchLogs();
    const interval = setInterval(fetchLogs, 2000);
    return () => clearInterval(interval);
  }, [isOpen]);

  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  // Resize handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    startY.current = e.clientY;
    startHeight.current = height;
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing) return;
      const delta = startY.current - e.clientY;
      const newHeight = Math.min(Math.max(startHeight.current + delta, 150), window.innerHeight - 100);
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
  }, [isResizing]);

  const clearLogs = async () => {
    try {
      await fetch(`${API_URL}/api/logs/clear`, { method: 'POST' });
      setLogs([]);
    } catch (e) {
      console.error('Clear logs error:', e);
    }
  };

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'success': return '#34D399';
      case 'warning': return '#FBBF24';
      case 'error': return '#F87171';
      default: return '#60A5FA';
    }
  };

  const getLevelIcon = (level: string) => {
    switch (level) {
      case 'success': return '✅';
      case 'warning': return '⚠️';
      case 'error': return '❌';
      default: return 'ℹ️';
    }
  };

  const formatTime = (timestamp: string) => {
    try {
      return new Date(timestamp).toLocaleTimeString('en-US', { 
        hour: '2-digit', 
        minute: '2-digit', 
        second: '2-digit',
        hour12: false,
      });
    } catch {
      return timestamp;
    }
  };

  return (
    <div 
      className="console-panel"
      style={{ 
        position: 'fixed',
        bottom: 0,
        left: 'var(--sidebar-width)',
        right: 0,
        zIndex: 200,
        transition: isResizing ? 'none' : 'left 0.2s ease',
      }}
    >
      {/* Resize Handle */}
      {isOpen && (
        <div
          onMouseDown={handleMouseDown}
          style={{
            height: 6,
            background: isResizing ? 'var(--accent-green)' : 'transparent',
            cursor: 'ns-resize',
            transition: 'background 0.15s ease',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-green)')}
          onMouseLeave={(e) => !isResizing && (e.currentTarget.style.background = 'transparent')}
        />
      )}

      {/* Toggle Bar */}
      <div 
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '12px 24px',
          background: 'var(--bg-secondary)',
          borderTop: '1px solid var(--border-primary)',
          cursor: 'pointer',
          fontSize: 13,
          fontWeight: 500,
          color: 'var(--text-secondary)',
          transition: 'all 0.15s ease',
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
        <div style={{
          background: '#0A0C10',
          borderTop: '1px solid var(--border-primary)',
          height: height,
          display: 'flex',
          flexDirection: 'column',
        }}>
          {/* Toolbar */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '8px 16px',
            background: '#0D0F14',
            borderBottom: '1px solid #1C2128',
          }}>
            <label style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              fontSize: 12,
              color: 'var(--text-muted)',
              cursor: 'pointer',
            }}>
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
              />
              Auto-scroll
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
              <button 
                onClick={fetchLogs}
                style={{
                  background: 'transparent',
                  border: '1px solid #30363D',
                  color: 'var(--text-muted)',
                  fontSize: 12,
                  padding: '4px 12px',
                  borderRadius: 4,
                  cursor: 'pointer',
                }}
              >
                🔄 Refresh
              </button>
              <button 
                onClick={clearLogs}
                style={{
                  background: 'transparent',
                  border: '1px solid #30363D',
                  color: 'var(--text-muted)',
                  fontSize: 12,
                  padding: '4px 12px',
                  borderRadius: 4,
                  cursor: 'pointer',
                }}
              >
                🗑️ Clear
              </button>
            </div>
          </div>

          {/* Logs */}
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
              <div style={{ 
                color: 'var(--text-muted)', 
                textAlign: 'center', 
                padding: 40,
              }}>
                No logs yet. Start an ETL or embedding job to see activity.
              </div>
            ) : (
              logs.map((log, idx) => (
                <div 
                  key={idx} 
                  style={{
                    display: 'flex',
                    gap: 12,
                    padding: '4px 0',
                    borderBottom: '1px solid rgba(48, 54, 61, 0.5)',
                  }}
                >
                  <span style={{ color: '#6E7681', flexShrink: 0, fontSize: 11 }}>
                    {formatTime(log.timestamp)}
                  </span>
                  <span style={{ flexShrink: 0, fontSize: 12 }}>
                    {getLevelIcon(log.level)}
                  </span>
                  <span style={{ color: getLevelColor(log.level) }}>
                    {log.message}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

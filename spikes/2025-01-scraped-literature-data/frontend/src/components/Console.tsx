/**
 * OARIA Literature - Console Panel
 * 
 * 실시간 로그 표시 (기본 닫힘)
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
  const logContainerRef = useRef<HTMLDivElement>(null);

  const fetchLogs = async () => {
    try {
      const res = await fetch(`${API_URL}/api/logs?limit=100`);
      if (res.ok) setLogs((await res.json()).logs || []);
    } catch (e) {
      console.error('Fetch logs error:', e);
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
      case 'success': return 'var(--accent-green)';
      case 'warning': return 'var(--warning)';
      case 'error': return 'var(--error)';
      default: return 'var(--accent-blue)';
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
    <div className={`console-panel ${isOpen ? 'open' : ''}`}>
      <div className="console-toggle" onClick={() => setIsOpen(!isOpen)}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span>🖥️</span> Console
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {logs.length > 0 && <span className="console-badge">{logs.length}</span>}
          <span style={{ fontSize: 12 }}>{isOpen ? '▼' : '▲'}</span>
        </span>
      </div>

      {isOpen && (
        <div className="console-content">
          <div className="console-toolbar">
            <label>
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
                style={{ marginRight: 6 }}
              />
              Auto-scroll
            </label>
            <button onClick={clearLogs} className="console-btn">
              🗑️ Clear
            </button>
          </div>

          <div className="console-logs" ref={logContainerRef}>
            {logs.length === 0 ? (
              <div className="console-empty">
                No logs yet. Start an ETL or embedding job to see activity.
              </div>
            ) : (
              logs.map((log, idx) => (
                <div key={idx} className="console-log-entry">
                  <span className="console-time">{formatTime(log.timestamp)}</span>
                  <span className="console-icon">{getLevelIcon(log.level)}</span>
                  <span style={{ color: getLevelColor(log.level) }}>{log.message}</span>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

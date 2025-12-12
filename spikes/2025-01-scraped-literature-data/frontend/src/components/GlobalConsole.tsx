/**
 * OARIA Enterprise — Global System Console
 * 
 * 모든 페이지에서 항상 표시되는 시스템 로그 패널
 * Apple Xcode Console + Notion Log 스타일
 * - SSE 자동 재연결
 * - 드래그 리사이즈
 * - 다크/라이트 모드 지원
 * - 지수 백오프 (에러 시 점진적 재시도 간격 증가)
 */

import { useState, useEffect, useRef, useCallback } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

// 지수 백오프 간격 (ms): 2초 → 10초 → 30초 → 1분 → 5분 → 30분 → 1시간
const BACKOFF_INTERVALS = [2000, 10000, 30000, 60000, 300000, 1800000, 3600000];

interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
  job_id?: string;
}

export default function GlobalConsole() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isOpen, setIsOpen] = useState(true);
  const [height, setHeight] = useState(220);
  const [isConnected, setIsConnected] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [isDragging, setIsDragging] = useState(false);
  const [reconnectCount, setReconnectCount] = useState(0);
  const [backoffLevel, setBackoffLevel] = useState(0);
  const [lastErrorTime, setLastErrorTime] = useState<number | null>(null);
  
  const consoleRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const dragStartY = useRef(0);
  const dragStartHeight = useRef(220);

  // 로그 로드 (에러 시 간략한 메시지 + 지수 백오프)
  const loadLogs = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/logs?limit=50`);
      if (res.ok) {
        const data = await res.json();
        setLogs(data.logs || []);
        // 성공 시 백오프 리셋
        setBackoffLevel(0);
        setLastErrorTime(null);
      }
    } catch (e: any) {
      const now = Date.now();
      // 마지막 에러 로그 후 최소 30초 경과 시에만 로그 출력
      if (!lastErrorTime || now - lastErrorTime > 30000) {
        const interval = BACKOFF_INTERVALS[Math.min(backoffLevel, BACKOFF_INTERVALS.length - 1)];
        console.warn(`⚠️ Backend unavailable (retry in ${interval / 1000}s)`);
        setLastErrorTime(now);
      }
      // 백오프 레벨 증가
      setBackoffLevel(prev => Math.min(prev + 1, BACKOFF_INTERVALS.length - 1));
    }
  }, [backoffLevel, lastErrorTime]);

  // SSE 연결
  const connectSSE = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    try {
      const es = new EventSource(`${API_URL}/api/console/stream`);
      
      es.onopen = () => {
        setIsConnected(true);
        setReconnectCount(0);
        setBackoffLevel(0); // 연결 성공 시 백오프 리셋
      };
      
      es.onmessage = (event) => {
        try {
          const log = JSON.parse(event.data);
          setLogs(prev => [...prev.slice(-150), log]);
        } catch (e) {
          // 파싱 에러는 무시 (간소화)
        }
      };
      
      es.onerror = () => {
        setIsConnected(false);
        es.close();
        eventSourceRef.current = null;
        
        // 자동 재연결 (지수 백오프)
        setReconnectCount(prev => {
          if (prev < 10) {
            const delay = BACKOFF_INTERVALS[Math.min(prev, BACKOFF_INTERVALS.length - 1)];
            setTimeout(connectSSE, delay);
            return prev + 1;
          }
          return prev;
        });
      };
      
      eventSourceRef.current = es;
    } catch (e) {
      // SSE 연결 에러는 간략히 처리
    }
  }, []);

  // 초기화
  useEffect(() => {
    loadLogs();
    connectSSE();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [loadLogs, connectSSE]);

  // Polling fallback (SSE 실패 시) - 지수 백오프 적용
  useEffect(() => {
    if (!isConnected) {
      const interval = BACKOFF_INTERVALS[Math.min(backoffLevel, BACKOFF_INTERVALS.length - 1)];
      const timer = setInterval(loadLogs, interval);
      return () => clearInterval(timer);
    }
  }, [isConnected, loadLogs, backoffLevel]);

  // 자동 스크롤
  useEffect(() => {
    if (autoScroll && consoleRef.current) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  // 드래그 리사이즈
  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    dragStartY.current = e.clientY;
    dragStartHeight.current = height;
    e.preventDefault();
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging) return;
      const deltaY = dragStartY.current - e.clientY;
      const newHeight = Math.min(Math.max(dragStartHeight.current + deltaY, 120), 500);
      setHeight(newHeight);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  // 로그 클리어
  const handleClear = async () => {
    try {
      await fetch(`${API_URL}/api/logs/clear`, { method: 'POST' });
      setLogs([]);
    } catch (e) {
      console.error('Clear error:', e);
    }
  };

  // 레벨별 스타일
  const getLevelStyle = (level: string) => {
    const styles: Record<string, { icon: string; color: string }> = {
      info: { icon: 'ℹ️', color: '#3B82F6' },
      success: { icon: '✅', color: '#10B981' },
      warning: { icon: '⚠️', color: '#F59E0B' },
      error: { icon: '❌', color: '#EF4444' },
      system: { icon: '🔧', color: '#8B5CF6' },
      etl: { icon: '🔄', color: '#06B6D4' },
      cron: { icon: '⏱️', color: '#EC4899' },
      db: { icon: '🗄️', color: '#14B8A6' },
    };
    return styles[level] || styles.info;
  };

  // 시간 포맷 (2025.12.13 PM 12:00:00)
  const formatTime = (timestamp: string) => {
    try {
      const date = new Date(timestamp);
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      const hours = date.getHours();
      const ampm = hours >= 12 ? 'PM' : 'AM';
      const h12 = hours % 12 || 12;
      const minutes = String(date.getMinutes()).padStart(2, '0');
      const seconds = String(date.getSeconds()).padStart(2, '0');
      return `${year}.${month}.${day} ${ampm} ${String(h12).padStart(2, '0')}:${minutes}:${seconds}`;
    } catch {
      return timestamp?.slice(11, 19) || '';
    }
  };

  // 미니 버튼 (닫힌 상태)
  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        style={{
          position: 'fixed',
          bottom: 20,
          right: 20,
          padding: '14px 24px',
          borderRadius: 14,
          background: 'var(--bg-secondary)',
          border: '1px solid var(--border-primary)',
          color: 'var(--text-primary)',
          fontSize: 14,
          fontWeight: 600,
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
          zIndex: 9999,
          backdropFilter: 'blur(20px)',
        }}
      >
        <span>🖥️</span>
        System Console
        <span style={{
          padding: '3px 10px',
          borderRadius: 12,
          background: isConnected ? 'rgba(16, 185, 129, 0.2)' : 'rgba(245, 158, 11, 0.2)',
          color: isConnected ? '#10B981' : '#F59E0B',
          fontSize: 11,
          fontWeight: 600,
        }}>
          {logs.length}
        </span>
      </button>
    );
  }

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 0,
        left: 260,
        right: 0,
        height: height,
        background: 'var(--bg-primary)',
        borderTop: '1px solid var(--border-primary)',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 9998,
        backdropFilter: 'blur(20px)',
        boxShadow: '0 -4px 32px rgba(0,0,0,0.15)',
      }}
    >
      {/* Resize Handle */}
      <div
        onMouseDown={handleMouseDown}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: 8,
          cursor: 'ns-resize',
          background: isDragging ? 'var(--accent-blue)' : 'transparent',
          transition: 'background 0.2s',
        }}
        onMouseEnter={(e) => {
          (e.target as HTMLDivElement).style.background = 'rgba(59, 130, 246, 0.5)';
        }}
        onMouseLeave={(e) => {
          if (!isDragging) {
            (e.target as HTMLDivElement).style.background = 'transparent';
          }
        }}
      />

      {/* Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '10px 20px',
        borderBottom: '1px solid var(--border-primary)',
        background: 'var(--bg-secondary)',
        userSelect: 'none',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 15, fontWeight: 700 }}>🖥️ OARIA System Console</span>
          <span style={{
            width: 10,
            height: 10,
            borderRadius: '50%',
            background: isConnected ? '#10B981' : '#F59E0B',
            boxShadow: isConnected ? '0 0 8px #10B981' : '0 0 8px #F59E0B',
          }} />
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            {isConnected ? 'Live Stream' : `Polling (retry ${reconnectCount})`} • {logs.length} entries
          </span>
        </div>
        
        <div style={{ display: 'flex', gap: 10 }}>
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            style={{
              padding: '6px 14px',
              borderRadius: 8,
              border: 'none',
              background: autoScroll ? 'var(--accent-blue)' : 'var(--bg-tertiary)',
              color: autoScroll ? '#fff' : 'var(--text-muted)',
              fontSize: 12,
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            {autoScroll ? '🔒 Locked' : '🔓 Unlocked'}
          </button>
          <button
            onClick={handleClear}
            style={{
              padding: '6px 14px',
              borderRadius: 8,
              border: 'none',
              background: 'var(--bg-tertiary)',
              color: 'var(--text-muted)',
              fontSize: 12,
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            🗑️ Clear
          </button>
          <button
            onClick={() => connectSSE()}
            style={{
              padding: '6px 14px',
              borderRadius: 8,
              border: 'none',
              background: 'var(--bg-tertiary)',
              color: 'var(--text-muted)',
              fontSize: 12,
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            🔄 Reconnect
          </button>
          <button
            onClick={() => setIsOpen(false)}
            style={{
              padding: '6px 14px',
              borderRadius: 8,
              border: 'none',
              background: 'var(--bg-tertiary)',
              color: 'var(--text-muted)',
              fontSize: 12,
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            ✕
          </button>
        </div>
      </div>

      {/* Logs */}
      <div
        ref={consoleRef}
        style={{
          flex: 1,
          overflow: 'auto',
          padding: 12,
          fontFamily: 'var(--font-mono)',
          fontSize: 12,
          lineHeight: 1.7,
        }}
        onScroll={(e) => {
          const el = e.currentTarget;
          const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50;
          if (isAtBottom !== autoScroll) {
            setAutoScroll(isAtBottom);
          }
        }}
      >
        {logs.length === 0 ? (
          <div style={{ 
            textAlign: 'center', 
            padding: 50, 
            color: 'var(--text-muted)',
            fontSize: 14,
          }}>
            🖥️ Console is empty — System logs will appear here
          </div>
        ) : (
          logs.map((log, idx) => {
            const style = getLevelStyle(log.level);
            return (
              <div
                key={`${log.timestamp}-${idx}`}
                style={{
                  padding: '5px 10px',
                  borderRadius: 6,
                  marginBottom: 3,
                  background: log.level === 'error' 
                    ? 'rgba(239, 68, 68, 0.1)' 
                    : log.level === 'success' 
                    ? 'rgba(16, 185, 129, 0.05)' 
                    : 'transparent',
                }}
              >
                <span style={{ color: 'var(--text-muted)' }}>
                  [{formatTime(log.timestamp)}]
                </span>{' '}
                <span>{style.icon}</span>{' '}
                <span style={{ color: style.color }}>{log.message}</span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

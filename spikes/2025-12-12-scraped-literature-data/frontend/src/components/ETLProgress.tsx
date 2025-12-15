/**
 * OARIA Literature - ETL Progress Component
 * 
 * 진행률 + ETA + 현재 단계 표시
 */

import { useEffect, useState } from 'react';

interface ETLProgressProps {
  status: 'idle' | 'running' | 'completed' | 'error' | 'stopped';
  progress: number;
  collected: number;
  total: number;
  message?: string;
  startTime?: number;
  onRetry?: () => void;
}

export default function ETLProgress({
  status,
  progress,
  collected,
  total,
  message,
  startTime,
  onRetry,
}: ETLProgressProps) {
  const [eta, setEta] = useState<string>('');

  // ETA 계산
  useEffect(() => {
    if (status !== 'running' || !startTime || progress <= 0) {
      setEta('');
      return;
    }

    const elapsed = Date.now() - startTime;
    const rate = progress / elapsed; // % per ms
    const remaining = (100 - progress) / rate;
    
    if (remaining > 0 && remaining < 3600000) { // 1시간 미만
      const mins = Math.floor(remaining / 60000);
      const secs = Math.floor((remaining % 60000) / 1000);
      setEta(mins > 0 ? `${mins}m ${secs}s remaining` : `${secs}s remaining`);
    } else {
      setEta('Calculating...');
    }
  }, [status, progress, startTime]);

  const getStatusConfig = () => {
    switch (status) {
      case 'running':
        return { 
          color: 'var(--accent-blue)', 
          bgColor: 'rgba(96, 165, 250, 0.1)',
          icon: '⏳',
          label: 'Running'
        };
      case 'completed':
        return { 
          color: 'var(--accent-green)', 
          bgColor: 'rgba(52, 211, 153, 0.1)',
          icon: '✅',
          label: 'Completed'
        };
      case 'error':
        return { 
          color: 'var(--error)', 
          bgColor: 'rgba(248, 113, 113, 0.1)',
          icon: '❌',
          label: 'Error'
        };
      case 'stopped':
        return { 
          color: 'var(--warning)', 
          bgColor: 'rgba(251, 191, 36, 0.1)',
          icon: '⏹️',
          label: 'Stopped'
        };
      default:
        return { 
          color: 'var(--text-muted)', 
          bgColor: 'var(--bg-tertiary)',
          icon: '⚪',
          label: 'Idle'
        };
    }
  };

  const config = getStatusConfig();

  if (status === 'idle') return null;

  return (
    <div 
      className="etl-progress"
      style={{
        padding: 20,
        borderRadius: 12,
        background: config.bgColor,
        border: `1px solid ${config.color}`,
        marginBottom: 24,
      }}
    >
      {/* Header */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        marginBottom: 16,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 20 }}>{config.icon}</span>
          <span style={{ 
            fontSize: 14, 
            fontWeight: 600, 
            color: config.color,
            textTransform: 'uppercase',
            letterSpacing: 0.5,
          }}>
            {config.label}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          {eta && (
            <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              ⏱️ {eta}
            </span>
          )}
          <span style={{ 
            fontSize: 20, 
            fontWeight: 700, 
            color: config.color,
            fontFamily: 'var(--font-mono)',
          }}>
            {progress.toFixed(1)}%
          </span>
        </div>
      </div>

      {/* Progress Bar */}
      <div style={{
        height: 8,
        borderRadius: 4,
        background: 'var(--bg-primary)',
        overflow: 'hidden',
        marginBottom: 12,
      }}>
        <div 
          style={{
            height: '100%',
            width: `${progress}%`,
            background: `linear-gradient(90deg, ${config.color}, ${config.color}CC)`,
            borderRadius: 4,
            transition: 'width 0.3s ease',
          }}
        />
      </div>

      {/* Stats */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        fontSize: 13,
        color: 'var(--text-secondary)',
      }}>
        <span>📊 Collected: {collected} / {total}</span>
        {message && (
          <span style={{ 
            maxWidth: '60%', 
            overflow: 'hidden', 
            textOverflow: 'ellipsis', 
            whiteSpace: 'nowrap',
          }}>
            {message}
          </span>
        )}
      </div>

      {/* Error + Retry */}
      {status === 'error' && onRetry && (
        <div style={{ marginTop: 16, display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ color: 'var(--error)', fontSize: 13 }}>
            {message || 'An error occurred'}
          </span>
          <button 
            onClick={onRetry}
            className="btn btn-primary"
            style={{ fontSize: 13, padding: '8px 16px' }}
          >
            🔄 Retry
          </button>
        </div>
      )}

      {/* Completed Message */}
      {status === 'completed' && (
        <div style={{ 
          marginTop: 16, 
          padding: 12, 
          background: 'var(--bg-primary)', 
          borderRadius: 8,
          fontSize: 13,
          color: 'var(--accent-green)',
        }}>
          🎉 Successfully collected {collected} papers! Check the Papers page for embedding processing.
        </div>
      )}
    </div>
  );
}

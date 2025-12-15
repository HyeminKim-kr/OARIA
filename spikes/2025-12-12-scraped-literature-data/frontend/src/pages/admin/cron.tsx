/**
 * OARIA Literature - Cron Logs
 * 
 * 크론 실행 기록 + 최근 7일 그래프
 * 모든 시간은 KST(한국시간)로 표시
 */

import { useState, useEffect } from 'react';
import Layout from '../../components/Layout';

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

interface CronLog {
  id: number;
  run_at: string;
  run_at_kst: string; // KST 변환된 시간
  keyword: string;
  fetched: number;
  inserted: number;
  skipped: number;
  duration_ms: number;
  status: string;
  error_message: string | null;
  pmid_range_start: string | null;
  pmid_range_end: string | null;
  offset_start: number;
  offset_end: number;
  db_before: number;
  db_after: number;
}

interface TodayStats {
  date: string;
  runs_today: number;
  successful_runs: number;
  failed_runs: number;
  inserted_today: number;
  skipped_today: number;
  papers_added_today: number;
  total_papers: number;
}

export default function CronLogs() {
  const [logs, setLogs] = useState<CronLog[]>([]);
  const [todayStats, setTodayStats] = useState<TodayStats | null>(null);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    setLoading(true);
    try {
      const [logsRes, statsRes] = await Promise.all([
        fetch(`${API_URL}/api/cron/logs?limit=100`),
        fetch(`${API_URL}/api/cron/stats/today`),
      ]);
      
      if (logsRes.ok) {
        const data = await logsRes.json();
        setLogs(data.logs);
      }
      if (statsRes.ok) {
        setTodayStats(await statsRes.json());
      }
    } catch (e) {
      console.error('Load error:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, []);

  // 최근 7일 그래프 데이터
  const last7Days = [...Array(7)].map((_, i) => {
    const date = new Date();
    date.setDate(date.getDate() - (6 - i));
    const dateStr = date.toISOString().split('T')[0];
    
    const dayLogs = logs.filter(log => {
      // KST 날짜 기준으로 필터
      const logDate = log.run_at_kst?.split(' ')[0];
      return logDate === dateStr;
    });
    const inserted = dayLogs.reduce((sum, log) => sum + log.inserted, 0);
    
    return {
      date: dateStr,
      label: date.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' }),
      inserted,
      runs: dayLogs.length,
    };
  });

  const maxInserted = Math.max(...last7Days.map(d => d.inserted), 1);

  return (
    <Layout title="Cron Logs" subtitle="크론 실행 기록 및 통계 (KST)">
      {/* Today Stats */}
      {todayStats && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 16,
          marginBottom: 24,
        }}>
          {[
            { label: 'Runs Today', value: todayStats.runs_today, icon: '🔄', color: '#3B82F6' },
            { label: 'Success', value: todayStats.successful_runs, icon: '✅', color: '#10B981' },
            { label: 'Failed', value: todayStats.failed_runs, icon: '❌', color: '#EF4444' },
            { label: 'Added Today', value: todayStats.inserted_today, icon: '📥', color: '#8B5CF6' },
          ].map((stat) => (
            <div key={stat.label} style={{
              padding: 20,
              borderRadius: 12,
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-primary)',
            }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
                {stat.icon} {stat.label}
              </div>
              <div style={{ fontSize: 28, fontWeight: 700, color: stat.color, fontFamily: 'var(--font-mono)' }}>
                {stat.value.toLocaleString()}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 7-Day Graph */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <div className="card-title"><span>📊</span> Last 7 Days</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, height: 150, padding: '16px 0' }}>
          {last7Days.map((day) => (
            <div key={day.date} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <div style={{ 
                fontSize: 11, 
                fontWeight: 600, 
                color: 'var(--accent-green)',
                marginBottom: 4,
              }}>
                {day.inserted > 0 ? day.inserted : ''}
              </div>
              <div style={{
                width: '100%',
                height: `${Math.max((day.inserted / maxInserted) * 100, 4)}px`,
                background: day.inserted > 0 ? 'linear-gradient(180deg, #10B981, #059669)' : 'var(--bg-tertiary)',
                borderRadius: 4,
                transition: 'height 0.3s ease',
              }} />
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>
                {day.label}
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                {day.runs > 0 && `${day.runs} runs`}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Log Table */}
      <div className="card" style={{ overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: 'var(--bg-tertiary)', fontSize: 12, textTransform: 'uppercase' }}>
              <th style={{ padding: 12, textAlign: 'left', fontWeight: 600, color: 'var(--text-muted)' }}>Time (KST)</th>
              <th style={{ padding: 12, textAlign: 'left', fontWeight: 600, color: 'var(--text-muted)' }}>Keyword</th>
              <th style={{ padding: 12, textAlign: 'left', fontWeight: 600, color: 'var(--text-muted)' }}>Inserted</th>
              <th style={{ padding: 12, textAlign: 'left', fontWeight: 600, color: 'var(--text-muted)' }}>Skipped</th>
              <th style={{ padding: 12, textAlign: 'left', fontWeight: 600, color: 'var(--text-muted)' }}>Offset</th>
              <th style={{ padding: 12, textAlign: 'left', fontWeight: 600, color: 'var(--text-muted)' }}>Duration</th>
              <th style={{ padding: 12, textAlign: 'left', fontWeight: 600, color: 'var(--text-muted)' }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
                  Loading...
                </td>
              </tr>
            ) : logs.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
                  No cron logs yet
                </td>
              </tr>
            ) : logs.map((log) => (
              <tr key={log.id} style={{ borderTop: '1px solid var(--border-primary)' }}>
                <td style={{ padding: 12, fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                  {/* KST 시간 표시 */}
                  {log.run_at_kst || log.run_at}
                </td>
                <td style={{ padding: 12, fontSize: 13 }}>
                  {log.keyword}
                </td>
                <td style={{ padding: 12, fontSize: 13, color: '#10B981', fontWeight: 600 }}>
                  +{log.inserted}
                </td>
                <td style={{ padding: 12, fontSize: 13, color: '#F59E0B' }}>
                  {log.skipped}
                </td>
                <td style={{ padding: 12, fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                  {log.offset_start}→{log.offset_end}
                </td>
                <td style={{ padding: 12, fontSize: 12, color: 'var(--text-muted)' }}>
                  {(log.duration_ms / 1000).toFixed(1)}s
                </td>
                <td style={{ padding: 12 }}>
                  <span style={{
                    padding: '4px 8px',
                    borderRadius: 4,
                    fontSize: 11,
                    fontWeight: 500,
                    background: log.status === 'success' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                    color: log.status === 'success' ? '#10B981' : '#EF4444',
                  }}>
                    {log.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Layout>
  );
}

/**
 * OARIA Literature - Premium Layout
 * 
 * Apple/Google급 사이드바 + 헤더 레이아웃 + 전역 콘솔
 */

import { useState, useEffect, ReactNode } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import GlobalConsole from './GlobalConsole';
import { useEnv, CustomDBParams } from '@/context/EnvContext';

interface LayoutProps {
  children: ReactNode;
  title?: string;
  subtitle?: string;
}

export default function Layout({ children, title, subtitle }: LayoutProps) {
  const router = useRouter();
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [collapsed, setCollapsed] = useState(false);
  const [showSwitchModal, setShowSwitchModal] = useState(false);
  const [isTestingConnection, setIsTestingConnection] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [customForm, setCustomForm] = useState<Omit<CustomDBParams, 'test_only'>>({
    host: '',
    port: 5432,
    database: '',
    username: '',
    password: '',
    db_type: 'postgresql',
  });
  const [customTestResult, setCustomTestResult] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  
  const API_URL = process.env.NEXT_PUBLIC_API_URL || '';
  
  // 전역 환경 상태 (Context 사용)
  const { envInfo, isLoading, isSwitching, switchError, switchMode, refreshEnv, connectCustom } = useEnv();

  useEffect(() => {
    const savedTheme = localStorage.getItem('oaria-theme') as 'dark' | 'light' | null;
    if (savedTheme) {
      setTheme(savedTheme);
      document.documentElement.setAttribute('data-theme', savedTheme);
    }
  }, []);

  const handleSwitchClick = () => {
    if (!envInfo?.supports_switching || isSwitching) return;
    setShowSwitchModal(true);
  };
  
  const handleSwitchConfirm = async () => {
    if (!envInfo) return;
    
    const newMode = envInfo.mode === 'local' ? 'gcp' : 'local';
    const success = await switchMode(newMode);
    
    if (success) {
      setShowSwitchModal(false);
    }
  };

  // DB 연결 테스트
  const handleTestConnection = async (e: React.MouseEvent) => {
    e.stopPropagation(); // 전환 모달 열리지 않게
    if (isTestingConnection || !envInfo) return;
    
    setIsTestingConnection(true);
    
    // 테스트 시작 로그
    try {
      await fetch(`${API_URL}/api/logs/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          level: 'db',
          message: `🔍 [${envInfo.mode.toUpperCase()}] ${envInfo.db_type === 'mysql' ? 'MySQL' : 'PostgreSQL'} 연결 테스트 중...`,
        }),
      });
    } catch {}
    
    try {
      const res = await fetch(`${API_URL}/api/health`);
      if (res.ok) {
        const data = await res.json();
        
        // 성공/실패 로그
        if (data.db_connected) {
          await fetch(`${API_URL}/api/logs/add`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              level: 'success',
              message: `[${data.mode.toUpperCase()}] ${data.db_type === 'mysql' ? 'MySQL' : 'PostgreSQL'} 연결 성공!`,
            }),
          });
        } else {
          await fetch(`${API_URL}/api/logs/add`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              level: 'error',
              message: `[${data.mode.toUpperCase()}] DB 연결 실패 - 서버 응답은 정상이나 DB 연결 불가`,
            }),
          });
        }
        
        // 상태 갱신
        await refreshEnv();
      } else {
        await fetch(`${API_URL}/api/logs/add`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            level: 'error',
            message: `❌ Health API 응답 오류: ${res.status}`,
          }),
        });
      }
    } catch (e: any) {
      await fetch(`${API_URL}/api/logs/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          level: 'error',
          message: `❌ 연결 테스트 실패: ${e.message || 'Network error'}`,
        }),
      }).catch(() => {});
    } finally {
      setIsTestingConnection(false);
    }
  };

  const toggleTheme = () => {
    const newTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('oaria-theme', newTheme);
  };

  const navItems = [
    { href: '/', icon: '🏠', label: 'Dashboard' },
    { href: '/etl', icon: '🚀', label: 'ETL Worker' },
    { href: '/dashboard', icon: '📊', label: 'Papers' },
    { href: '/evidence', icon: '🔍', label: 'Semantic Search' },
  ];

  const adminItems = [
    { href: '/admin/papers', icon: '📄', label: 'Paper Manager' },
    { href: '/admin/cron', icon: '⏱️', label: 'Cron Logs' },
    { href: '/admin/db', icon: '🗄️', label: 'DB Tables' },
  ];

  return (
    <div className="layout">
      {/* Sidebar */}
      <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
        <div className="sidebar-header">
          <div className="sidebar-logo">
            <div className="sidebar-logo-icon">🧬</div>
            {!collapsed && <span>OARIA</span>}
          </div>
          <button 
            className="btn-collapse" 
            onClick={() => setCollapsed(!collapsed)}
            title={collapsed ? 'Expand' : 'Collapse'}
          >
            {collapsed ? '→' : '←'}
          </button>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-section">
            {!collapsed && <div className="nav-section-title">Navigation</div>}
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`sidebar-link ${router.pathname === item.href ? 'active' : ''}`}
              >
                <span className="sidebar-icon">{item.icon}</span>
                {!collapsed && <span className="sidebar-label">{item.label}</span>}
              </Link>
            ))}
          </div>

          <div className="nav-section">
            {!collapsed && <div className="nav-section-title">Admin</div>}
            {adminItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`sidebar-link ${router.pathname === item.href ? 'active' : ''}`}
              >
                <span className="sidebar-icon">{item.icon}</span>
                {!collapsed && <span className="sidebar-label">{item.label}</span>}
              </Link>
            ))}
          </div>
        </nav>

        <div className="sidebar-footer">
          {/* 환경 표시 (GCP/Local + DB + 연결 상태) - 클릭 시 전환 */}
          {envInfo && (
            <button 
              className="sidebar-link"
              style={{ 
                cursor: envInfo.supports_switching ? 'pointer' : 'default',
                opacity: isSwitching ? 0.5 : 0.9,
                width: '100%',
                border: 'none',
                background: 'none',
                textAlign: 'left',
              }}
              onClick={handleSwitchClick}
              disabled={!envInfo.supports_switching || isSwitching}
              title={
                envInfo.mode === 'custom' && envInfo.custom_connection
                  ? `커스텀: ${envInfo.custom_connection.host}:${envInfo.custom_connection.port}`
                  : envInfo.supports_switching 
                    ? `클릭하여 ${envInfo.mode === 'local' ? 'GCP' : 'LOCAL'}로 전환`
                    : `Mode: ${envInfo.mode.toUpperCase()} | DB: ${envInfo.db_type}`
              }
            >
              <span className="sidebar-icon">
                {isSwitching ? '⏳' : (
                  envInfo.mode === 'custom' ? '🔗' :
                  envInfo.mode === 'gcp' ? '☁️' : '💻'
                )}
              </span>
              {!collapsed && (
                <span className="sidebar-label" style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: 6,
                  fontSize: 12,
                }}>
                  <span style={{ 
                    padding: '2px 8px', 
                    borderRadius: 6, 
                    background: envInfo.mode === 'custom' 
                      ? 'rgba(168, 85, 247, 0.2)'
                      : envInfo.mode === 'gcp' 
                        ? 'rgba(59, 130, 246, 0.2)' 
                        : 'rgba(16, 185, 129, 0.2)',
                    color: envInfo.mode === 'custom' 
                      ? '#A855F7'
                      : envInfo.mode === 'gcp' ? '#3B82F6' : '#10B981',
                    fontWeight: 600,
                    maxWidth: 80,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}>
                    {envInfo.mode === 'custom' && envInfo.custom_connection 
                      ? `${envInfo.custom_connection.host}` 
                      : envInfo.mode.toUpperCase()}
                    {envInfo.supports_switching && envInfo.mode !== 'custom' && ' ⇋'}
                  </span>
                  <span 
                    onClick={handleTestConnection}
                    title="클릭하여 DB 연결 테스트"
                    style={{ 
                      padding: '2px 6px', 
                      borderRadius: 4, 
                      background: 'var(--bg-tertiary)',
                      color: 'var(--text-muted)',
                      fontSize: 10,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                      cursor: 'pointer',
                      opacity: isTestingConnection ? 0.6 : 1,
                      transition: 'all 0.2s ease',
                    }}>
                    <span style={{
                      width: 6,
                      height: 6,
                      borderRadius: '50%',
                      background: isLoading 
                        ? '#F59E0B'  // 로딩 중 노란색
                        : isTestingConnection 
                          ? '#3B82F6'  // 테스트 중 파란색
                          : envInfo.db_connected 
                            ? '#10B981' 
                            : '#EF4444',
                      boxShadow: `0 0 4px ${
                        isLoading ? '#F59E0B' 
                        : isTestingConnection ? '#3B82F6' 
                        : envInfo.db_connected ? '#10B981' : '#EF4444'
                      }`,
                      animation: isTestingConnection ? 'pulse 1s infinite' : 'none',
                    }} />
                    {isTestingConnection ? '...' : (envInfo.db_type === 'mysql' ? 'MySQL' : 'PG')}
                  </span>
                </span>
              )}
            </button>
          )}
          
          <button 
            className="sidebar-link"
            onClick={toggleTheme}
            title={theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
          >
            <span className="sidebar-icon">{theme === 'dark' ? '☀️' : '🌙'}</span>
            {!collapsed && <span className="sidebar-label">{theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</span>}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        {title && (
          <header className="page-header">
            <h1>{title}</h1>
            {subtitle && <p>{subtitle}</p>}
          </header>
        )}
        <div className="page-content" style={{ paddingBottom: 220 }}>
          {children}
        </div>
      </main>

      {/* 전역 콘솔 */}
      <GlobalConsole />

      {/* DB 스위칭 모달 */}
      {showSwitchModal && envInfo && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.6)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 10000,
        }}>
          <div style={{
            background: 'var(--bg-primary)',
            borderRadius: 16,
            padding: 24,
            maxWidth: 400,
            width: '90%',
            boxShadow: '0 20px 60px rgba(0, 0, 0, 0.3)',
          }}>
            <div style={{ fontSize: 20, fontWeight: 600, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
              🔄 DB 모드 전환
            </div>
            
            <div style={{ marginBottom: 20, color: 'var(--text-secondary)' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12, padding: 16, background: 'var(--bg-tertiary)', borderRadius: 12, marginBottom: 12 }}>
                <span style={{ padding: '6px 12px', borderRadius: 8, background: envInfo.mode === 'local' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(59, 130, 246, 0.2)', color: envInfo.mode === 'local' ? '#10B981' : '#3B82F6', fontWeight: 600 }}>
                  {envInfo.mode === 'local' ? '💻 LOCAL' : '☁️ GCP'}
                </span>
                <span style={{ fontSize: 18 }}>→</span>
                <span style={{ padding: '6px 12px', borderRadius: 8, background: envInfo.mode === 'local' ? 'rgba(59, 130, 246, 0.2)' : 'rgba(16, 185, 129, 0.2)', color: envInfo.mode === 'local' ? '#3B82F6' : '#10B981', fontWeight: 600 }}>
                  {envInfo.mode === 'local' ? '☁️ GCP' : '💻 LOCAL'}
                </span>
              </div>
              <div style={{ fontSize: 13, textAlign: 'center' }}>
                데이터베이스 연결이 전환됩니다.
              </div>
            </div>

            {/* 고급 설정 (접기/펼치기) */}
            <div style={{ marginBottom: 16 }}>
              <button
                onClick={() => setShowAdvanced(!showAdvanced)}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  borderRadius: 8,
                  border: '1px dashed var(--border-primary)',
                  background: 'transparent',
                  color: 'var(--text-secondary)',
                  fontSize: 13,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                }}
              >
                <span>{showAdvanced ? '▼' : '▶'}</span>
                고급 설정 - 커스텀 DB 연결
              </button>
              
              {showAdvanced && (
                <div style={{ marginTop: 12, padding: 16, background: 'var(--bg-tertiary)', borderRadius: 12 }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                    <div>
                      <label style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4, display: 'block' }}>Host</label>
                      <input
                        type="text"
                        value={customForm.host}
                        onChange={(e) => setCustomForm({ ...customForm, host: e.target.value })}
                        placeholder="db.example.com"
                        style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid var(--border-primary)', background: 'var(--bg-primary)', color: 'var(--text-primary)', fontSize: 12 }}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4, display: 'block' }}>Port</label>
                      <input
                        type="number"
                        value={customForm.port}
                        onChange={(e) => setCustomForm({ ...customForm, port: parseInt(e.target.value) || 5432 })}
                        style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid var(--border-primary)', background: 'var(--bg-primary)', color: 'var(--text-primary)', fontSize: 12 }}
                      />
                    </div>
                  </div>
                  
                  <div style={{ marginBottom: 12 }}>
                    <label style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4, display: 'block' }}>Database</label>
                    <input
                      type="text"
                      value={customForm.database}
                      onChange={(e) => setCustomForm({ ...customForm, database: e.target.value })}
                      placeholder="oaria"
                      style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid var(--border-primary)', background: 'var(--bg-primary)', color: 'var(--text-primary)', fontSize: 12 }}
                    />
                  </div>
                  
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                    <div>
                      <label style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4, display: 'block' }}>Username</label>
                      <input
                        type="text"
                        value={customForm.username}
                        onChange={(e) => setCustomForm({ ...customForm, username: e.target.value })}
                        placeholder="admin"
                        style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid var(--border-primary)', background: 'var(--bg-primary)', color: 'var(--text-primary)', fontSize: 12 }}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4, display: 'block' }}>Password</label>
                      <input
                        type="password"
                        value={customForm.password}
                        onChange={(e) => setCustomForm({ ...customForm, password: e.target.value })}
                        placeholder="••••••"
                        style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid var(--border-primary)', background: 'var(--bg-primary)', color: 'var(--text-primary)', fontSize: 12 }}
                      />
                    </div>
                  </div>
                  
                  <div style={{ marginBottom: 12 }}>
                    <label style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4, display: 'block' }}>DB Type</label>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button
                        onClick={() => setCustomForm({ ...customForm, db_type: 'postgresql', port: 5432 })}
                        style={{
                          flex: 1,
                          padding: '8px',
                          borderRadius: 6,
                          border: customForm.db_type === 'postgresql' ? '2px solid #10B981' : '1px solid var(--border-primary)',
                          background: customForm.db_type === 'postgresql' ? 'rgba(16, 185, 129, 0.1)' : 'transparent',
                          color: customForm.db_type === 'postgresql' ? '#10B981' : 'var(--text-secondary)',
                          fontSize: 12,
                          fontWeight: 500,
                          cursor: 'pointer',
                        }}
                      >
                        🐘 PostgreSQL
                      </button>
                      <button
                        onClick={() => setCustomForm({ ...customForm, db_type: 'mysql', port: 3306 })}
                        style={{
                          flex: 1,
                          padding: '8px',
                          borderRadius: 6,
                          border: customForm.db_type === 'mysql' ? '2px solid #F59E0B' : '1px solid var(--border-primary)',
                          background: customForm.db_type === 'mysql' ? 'rgba(245, 158, 11, 0.1)' : 'transparent',
                          color: customForm.db_type === 'mysql' ? '#F59E0B' : 'var(--text-secondary)',
                          fontSize: 12,
                          fontWeight: 500,
                          cursor: 'pointer',
                        }}
                      >
                        🐬 MySQL
                      </button>
                    </div>
                  </div>
                  
                  {/* 연결 테스트 결과 */}
                  {customTestResult !== 'idle' && (
                    <div style={{
                      padding: 8,
                      borderRadius: 6,
                      marginBottom: 12,
                      fontSize: 12,
                      background: customTestResult === 'success' ? 'rgba(16, 185, 129, 0.1)' : customTestResult === 'error' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(59, 130, 246, 0.1)',
                      color: customTestResult === 'success' ? '#10B981' : customTestResult === 'error' ? '#EF4444' : '#3B82F6',
                    }}>
                      {customTestResult === 'testing' && '⏳ 연결 테스트 중...'}
                      {customTestResult === 'success' && '✅ 연결 성공!'}
                      {customTestResult === 'error' && '❌ 연결 실패'}
                    </div>
                  )}
                  
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button
                      onClick={async () => {
                        setCustomTestResult('testing');
                        const success = await connectCustom({ ...customForm, test_only: true });
                        setCustomTestResult(success ? 'success' : 'error');
                      }}
                      disabled={!customForm.host || !customForm.database || !customForm.username || isSwitching}
                      style={{
                        flex: 1,
                        padding: '10px',
                        borderRadius: 8,
                        border: '1px solid var(--border-primary)',
                        background: 'transparent',
                        color: 'var(--text-primary)',
                        fontSize: 12,
                        fontWeight: 500,
                        cursor: 'pointer',
                        opacity: (!customForm.host || !customForm.database || !customForm.username) ? 0.5 : 1,
                      }}
                    >
                      🔍 연결 테스트
                    </button>
                    <button
                      onClick={async () => {
                        const success = await connectCustom({ ...customForm, test_only: false });
                        if (success) {
                          setShowSwitchModal(false);
                          setShowAdvanced(false);
                        }
                      }}
                      disabled={!customForm.host || !customForm.database || !customForm.username || isSwitching}
                      style={{
                        flex: 1,
                        padding: '10px',
                        borderRadius: 8,
                        border: 'none',
                        background: 'linear-gradient(135deg, #A855F7, #6366F1)',
                        color: '#fff',
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: 'pointer',
                        opacity: (!customForm.host || !customForm.database || !customForm.username) ? 0.5 : 1,
                      }}
                    >
                      🔗 연결하기
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* 에러 표시 */}
            {switchError && (
              <div style={{ padding: 12, background: 'rgba(239, 68, 68, 0.1)', borderRadius: 8, marginBottom: 16, color: '#EF4444', fontSize: 13 }}>
                <strong>❌ 전환 실패:</strong> {switchError}
              </div>
            )}
            
            <div style={{ display: 'flex', gap: 12 }}>
              <button
                onClick={() => { setShowSwitchModal(false); setShowAdvanced(false); }}
                disabled={isSwitching}
                style={{
                  flex: 1,
                  padding: '12px 20px',
                  borderRadius: 10,
                  border: '1px solid var(--border-primary)',
                  background: 'transparent',
                  color: 'var(--text-primary)',
                  fontSize: 14,
                  fontWeight: 500,
                  cursor: isSwitching ? 'not-allowed' : 'pointer',
                  opacity: isSwitching ? 0.5 : 1,
                }}
              >
                취소
              </button>
              <button
                onClick={handleSwitchConfirm}
                disabled={isSwitching}
                style={{
                  flex: 1,
                  padding: '12px 20px',
                  borderRadius: 10,
                  border: 'none',
                  background: 'linear-gradient(135deg, #3B82F6, #10B981)',
                  color: '#fff',
                  fontSize: 14,
                  fontWeight: 600,
                  cursor: isSwitching ? 'not-allowed' : 'pointer',
                  opacity: isSwitching ? 0.7 : 1,
                }}
              >
                {isSwitching ? '⏳ 전환 중...' : `${envInfo.mode === 'local' ? 'GCP' : 'LOCAL'}로 전환`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * OARIA Literature - Premium Layout
 * 
 * Apple/Google급 사이드바 + 헤더 레이아웃
 */

import { useState, useEffect, ReactNode } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Console from './Console';

interface LayoutProps {
  children: ReactNode;
  title?: string;
  subtitle?: string;
}

export default function Layout({ children, title, subtitle }: LayoutProps) {
  const router = useRouter();
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const savedTheme = localStorage.getItem('oaria-theme') as 'dark' | 'light' | null;
    if (savedTheme) {
      setTheme(savedTheme);
      document.documentElement.setAttribute('data-theme', savedTheme);
    }
  }, []);

  const toggleTheme = () => {
    const newTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('oaria-theme', newTheme);
  };

  const navItems = [
    { href: '/', icon: '🏠', label: 'Dashboard' },
    { href: '/dashboard', icon: '📊', label: 'Papers' },
    { href: '/evidence', icon: '🔍', label: 'Semantic Search' },
    { href: '/guide', icon: '📖', label: 'Guide' },
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
        </nav>

        <div className="sidebar-footer">
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
        <div className="page-content" style={{ paddingBottom: 80 }}>
          {children}
        </div>
      </main>

      {/* Console */}
      <Console />
    </div>
  );
}

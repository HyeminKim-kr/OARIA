/**
 * OARIA Literature - App Component
 * 
 * 글로벌 스타일과 레이아웃 적용
 */

import type { AppProps } from 'next/app';
import { useEffect } from 'react';
import { EnvProvider } from '@/context/EnvContext';
import '@/styles/globals.css';

export default function App({ Component, pageProps }: AppProps) {
  // 초기 테마 로드
  useEffect(() => {
    const savedTheme = localStorage.getItem('oaria-theme') as 'dark' | 'light' | null;
    if (savedTheme) {
      document.documentElement.setAttribute('data-theme', savedTheme);
    }
  }, []);

  return (
    <EnvProvider>
      <Component {...pageProps} />
    </EnvProvider>
  );
}

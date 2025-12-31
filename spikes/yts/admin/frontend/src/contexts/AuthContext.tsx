'use client';

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useRef,
  ReactNode,
} from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { api } from '@/lib/api';

export interface AdminUser {
  id: string;
  email: string;
  name: string;
  picture: string;
  status: 'pending' | 'approved' | 'rejected';
  role: 'super_admin' | 'admin' | 'viewer';
  createdAt: string;
  lastLoginAt: string | null;
}

interface AuthContextType {
  user: AdminUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isSuperAdmin: boolean;
  isRedirecting: boolean;
  login: () => void;
  logout: () => void;
  refreshTokens: () => Promise<boolean>;
  handleOAuthCallback: (accessToken: string, refreshToken: string) => Promise<boolean>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const PUBLIC_PATHS = ['/auth', '/auth/callback', '/auth/pending', '/auth/rejected'];

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AdminUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRedirecting, setIsRedirecting] = useState(false);
  const isRedirectingRef = useRef(false);
  const router = useRouter();
  const pathname = usePathname();

  // 토큰 저장
  const saveTokens = useCallback((accessToken: string, refreshToken: string) => {
    localStorage.setItem('accessToken', accessToken);
    localStorage.setItem('refreshToken', refreshToken);
    api.defaults.headers.common['Authorization'] = `Bearer ${accessToken}`;
  }, []);

  // 토큰 삭제
  const clearTokens = useCallback(() => {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    delete api.defaults.headers.common['Authorization'];
  }, []);

  // 토큰 갱신
  const refreshTokens = useCallback(async (): Promise<boolean> => {
    const refreshToken = localStorage.getItem('refreshToken');
    if (!refreshToken) return false;

    try {
      const response = await api.post<{
        accessToken: string;
        refreshToken: string;
        user: AdminUser;
      }>('/auth/refresh', { refreshToken });

      saveTokens(response.data.accessToken, response.data.refreshToken);
      setUser(response.data.user);
      return true;
    } catch {
      clearTokens();
      setUser(null);
      return false;
    }
  }, [saveTokens, clearTokens]);

  // 현재 사용자 정보 가져오기
  const fetchUser = useCallback(async () => {
    const accessToken = localStorage.getItem('accessToken');
    if (!accessToken) {
      setIsLoading(false);
      return;
    }

    api.defaults.headers.common['Authorization'] = `Bearer ${accessToken}`;

    try {
      const response = await api.get<AdminUser>('/auth/me');
      setUser(response.data);
    } catch (error: unknown) {
      // 401이면 토큰 갱신 시도
      if ((error as { response?: { status?: number } })?.response?.status === 401) {
        const refreshed = await refreshTokens();
        if (!refreshed) {
          clearTokens();
        }
      } else {
        clearTokens();
      }
    } finally {
      setIsLoading(false);
    }
  }, [refreshTokens, clearTokens]);

  // 로그인
  const login = useCallback(() => {
    // 이미 리다이렉트 중이면 무시
    if (isRedirectingRef.current) return;

    isRedirectingRef.current = true;
    setIsRedirecting(true);

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:13000';
    window.location.href = `${apiUrl}/auth/google`;
  }, []);

  // 로그아웃
  const logout = useCallback(async () => {
    const refreshToken = localStorage.getItem('refreshToken');
    if (refreshToken) {
      try {
        await api.post('/auth/logout', { refreshToken });
      } catch {
        // 무시
      }
    }
    clearTokens();
    setUser(null);
    router.push('/auth');
  }, [clearTokens, router]);

  // OAuth 콜백 처리 (토큰 저장 + 사용자 정보 가져오기)
  const handleOAuthCallback = useCallback(async (accessToken: string, refreshToken: string): Promise<boolean> => {
    saveTokens(accessToken, refreshToken);

    try {
      const response = await api.get<AdminUser>('/auth/me');
      setUser(response.data);
      setIsLoading(false);
      return true;
    } catch {
      clearTokens();
      setUser(null);
      setIsLoading(false);
      return false;
    }
  }, [saveTokens, clearTokens]);

  // 초기화
  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  // 인증 상태에 따른 리다이렉트
  useEffect(() => {
    // 외부 리다이렉트(Google OAuth) 중이면 내부 라우팅 안 함
    if (isLoading || isRedirectingRef.current) return;

    const isPublicPath = PUBLIC_PATHS.some((path) => pathname.startsWith(path));

    if (!user && !isPublicPath) {
      router.push('/auth');
    } else if (user && pathname === '/auth') {
      router.push('/');
    }
  }, [user, isLoading, pathname, router]);

  // API 401 인터셉터
  useEffect(() => {
    const interceptor = api.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error.config;

        if (
          error.response?.status === 401 &&
          !originalRequest._retry &&
          !originalRequest.url?.includes('/auth/')
        ) {
          originalRequest._retry = true;
          const refreshed = await refreshTokens();
          if (refreshed) {
            return api(originalRequest);
          }
          logout();
        }

        return Promise.reject(error);
      }
    );

    return () => {
      api.interceptors.response.eject(interceptor);
    };
  }, [refreshTokens, logout]);

  const value: AuthContextType = {
    user,
    isLoading,
    isAuthenticated: !!user,
    isSuperAdmin: user?.role === 'super_admin',
    isRedirecting,
    login,
    logout,
    refreshTokens,
    handleOAuthCallback,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

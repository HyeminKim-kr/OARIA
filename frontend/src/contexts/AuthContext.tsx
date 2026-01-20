"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  ReactNode,
} from "react";
import { User, AuthState } from "@/types/auth";
import { authApi } from "@/lib/api";

interface AuthContextType extends AuthState {
  login: () => void;
  logout: () => Promise<void>;
  setTokens: (accessToken: string, refreshToken: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    accessToken: null,
    refreshToken: null,
    isLoading: true,
    isAuthenticated: false,
  });

  // 초기 로드: localStorage에서 토큰 복원
  useEffect(() => {
    const initAuth = async () => {
      if (typeof window === "undefined") return;

      const accessToken = localStorage.getItem("access_token");
      const refreshToken = localStorage.getItem("refresh_token");
      const userStr = localStorage.getItem("user");

      if (accessToken && refreshToken) {
        try {
          // 저장된 유저 정보가 있으면 먼저 사용
          const cachedUser = userStr ? JSON.parse(userStr) : null;

          setState({
            user: cachedUser,
            accessToken,
            refreshToken,
            isLoading: true,
            isAuthenticated: !!cachedUser,
          });

          // API로 최신 유저 정보 가져오기
          const response = await authApi.getMe();
          const user = response.data;
          localStorage.setItem("user", JSON.stringify(user));

          setState({
            user,
            accessToken,
            refreshToken,
            isLoading: false,
            isAuthenticated: true,
          });
        } catch (error) {
          // 토큰 만료 또는 유효하지 않음
          console.error("Failed to restore auth:", error);
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          localStorage.removeItem("user");

          setState({
            user: null,
            accessToken: null,
            refreshToken: null,
            isLoading: false,
            isAuthenticated: false,
          });
        }
      } else {
        setState((prev) => ({ ...prev, isLoading: false }));
      }
    };

    initAuth();
  }, []);

  // Google OAuth 로그인 시작
  const login = useCallback(() => {
    window.location.href = `${API_BASE_URL}/auth/google`;
  }, []);

  // 로그아웃
  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch (error) {
      console.error("Logout error:", error);
    } finally {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      localStorage.removeItem("user");

      setState({
        user: null,
        accessToken: null,
        refreshToken: null,
        isLoading: false,
        isAuthenticated: false,
      });
    }
  }, []);

  // OAuth 콜백에서 토큰 설정
  const setTokens = useCallback(
    async (accessToken: string, refreshToken: string) => {
      localStorage.setItem("access_token", accessToken);
      localStorage.setItem("refresh_token", refreshToken);

      setState((prev) => ({
        ...prev,
        accessToken,
        refreshToken,
        isLoading: true,
      }));

      try {
        const response = await authApi.getMe();
        const user: User = response.data;
        localStorage.setItem("user", JSON.stringify(user));

        setState({
          user,
          accessToken,
          refreshToken,
          isLoading: false,
          isAuthenticated: true,
        });
      } catch (error) {
        console.error("Failed to get user info:", error);
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");

        setState({
          user: null,
          accessToken: null,
          refreshToken: null,
          isLoading: false,
          isAuthenticated: false,
        });
        throw error;
      }
    },
    []
  );

  return (
    <AuthContext.Provider value={{ ...state, login, logout, setTokens }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

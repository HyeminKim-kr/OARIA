/**
 * 환경 상태 Context
 * 
 * DB 모드, 연결 상태 등을 전역으로 관리
 * 스위칭 시 새로고침 없이 UI 업데이트
 */

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

export interface CustomConnection {
  host: string;
  port: number;
  database: string;
  connected_at?: string;
}

export interface EnvInfo {
  mode: 'local' | 'gcp' | 'custom';
  db_type: 'mysql' | 'postgresql';
  db_connected: boolean;
  supports_switching: boolean;
  custom_connection?: CustomConnection;
}

export interface CustomDBParams {
  host: string;
  port: number;
  database: string;
  username: string;
  password: string;
  db_type: 'postgresql' | 'mysql';
  test_only?: boolean;
}

interface EnvContextType {
  envInfo: EnvInfo | null;
  isLoading: boolean;
  isSwitching: boolean;
  switchError: string | null;
  refreshEnv: () => Promise<void>;
  switchMode: (newMode: 'local' | 'gcp') => Promise<boolean>;
  connectCustom: (params: CustomDBParams) => Promise<boolean>;
}

const EnvContext = createContext<EnvContextType | null>(null);

export function EnvProvider({ children }: { children: React.ReactNode }) {
  const [envInfo, setEnvInfo] = useState<EnvInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSwitching, setIsSwitching] = useState(false);
  const [switchError, setSwitchError] = useState<string | null>(null);

  // 환경 정보 갱신
  const refreshEnv = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/health`);
      if (res.ok) {
        const data = await res.json();
        setEnvInfo({
          mode: data.mode,
          db_type: data.db_type,
          db_connected: data.db_connected ?? false,
          supports_switching: data.supports_switching ?? false,
        });
      }
    } catch {
      // 연결 실패 시 db_connected = false
      if (envInfo) {
        setEnvInfo({ ...envInfo, db_connected: false });
      }
    } finally {
      setIsLoading(false);
    }
  }, [envInfo]);

  // 초기 로드
  useEffect(() => {
    refreshEnv();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // DB 모드 전환
  const switchMode = useCallback(async (newMode: 'local' | 'gcp'): Promise<boolean> => {
    if (!envInfo?.supports_switching || isSwitching) return false;
    
    setIsSwitching(true);
    setSwitchError(null);

    // 시작 로그
    try {
      await fetch(`${API_URL}/api/logs/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          level: 'db',
          message: `🔄 DB 전환 시작: ${envInfo.mode.toUpperCase()} → ${newMode.toUpperCase()}...`,
        }),
      });
    } catch {}

    try {
      const res = await fetch(`${API_URL}/api/db/switch?mode=${newMode}`, {
        method: 'POST',
      });

      if (res.ok) {
        const result = await res.json();
        
        // 성공 로그
        try {
          await fetch(`${API_URL}/api/logs/add`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              level: 'success',
              message: `✅ DB 전환 완료: ${result.old_mode?.toUpperCase()} → ${result.new_mode?.toUpperCase()} (${result.db_type})`,
            }),
          });
        } catch {}

        // 상태 업데이트 (새로고침 없이!)
        setEnvInfo({
          mode: result.new_mode,
          db_type: result.db_type,
          db_connected: result.connected,
          supports_switching: true,
        });
        
        setIsSwitching(false);
        return true;
      } else {
        const err = await res.json();
        const errorMsg = err.detail || 'Unknown error';
        setSwitchError(errorMsg);

        // 에러 로그
        try {
          await fetch(`${API_URL}/api/logs/add`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              level: 'error',
              message: `❌ DB 전환 실패: ${errorMsg}`,
            }),
          });
        } catch {}
        
        setIsSwitching(false);
        return false;
      }
    } catch (e: any) {
      const errorMsg = e.message || 'Network error';
      setSwitchError(errorMsg);

      try {
        await fetch(`${API_URL}/api/logs/add`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            level: 'error',
            message: `❌ DB 전환 실패: ${errorMsg}`,
          }),
        });
      } catch {}
      
      setIsSwitching(false);
      return false;
    }
  }, [envInfo, isSwitching]);

  // 커스텀 DB 연결
  const connectCustom = useCallback(async (params: CustomDBParams): Promise<boolean> => {
    setIsSwitching(true);
    setSwitchError(null);

    try {
      await fetch(`${API_URL}/api/logs/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          level: 'db',
          message: `🔗 커스텀 DB ${params.test_only ? '테스트' : '연결'} 중: ${params.host}:${params.port}/${params.database}`,
        }),
      });
    } catch {}

    try {
      const res = await fetch(`${API_URL}/api/db/connect-custom`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      });

      if (res.ok) {
        const result = await res.json();
        
        if (params.test_only) {
          // 테스트만 한 경우 상태 변경 없이 성공 반환
          setIsSwitching(false);
          return true;
        }

        // 연결 성공 시 상태 업데이트
        setEnvInfo({
          mode: 'custom',
          db_type: params.db_type,
          db_connected: true,
          supports_switching: true,
          custom_connection: {
            host: result.host,
            port: result.port,
            database: result.database,
            connected_at: new Date().toISOString(),
          },
        });
        
        setIsSwitching(false);
        return true;
      } else {
        const err = await res.json();
        const errorMsg = err.detail || 'Connection failed';
        setSwitchError(errorMsg);
        setIsSwitching(false);
        return false;
      }
    } catch (e: any) {
      const errorMsg = e.message || 'Network error';
      setSwitchError(errorMsg);
      setIsSwitching(false);
      return false;
    }
  }, []);

  return (
    <EnvContext.Provider value={{
      envInfo,
      isLoading,
      isSwitching,
      switchError,
      refreshEnv,
      switchMode,
      connectCustom,
    }}>
      {children}
    </EnvContext.Provider>
  );
}

export function useEnv() {
  const context = useContext(EnvContext);
  if (!context) {
    throw new Error('useEnv must be used within EnvProvider');
  }
  return context;
}

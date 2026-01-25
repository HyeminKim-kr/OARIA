"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useRef,
  ReactNode,
} from "react";
import {
  NotificationItem,
  notificationsApi,
  fetchWithAuth,
} from "@/lib/api";
import { useAuth } from "./AuthContext";

// Toast 타입
export interface Toast {
  id: string;
  type: "info" | "success" | "warning" | "error";
  title: string;
  message: string;
  duration?: number; // ms, undefined면 자동 닫힘 없음
  action?: {
    label: string;
    onClick: () => void;
  };
}

interface NotificationContextType {
  // 알림 목록
  notifications: NotificationItem[];
  unreadCount: number;
  isLoading: boolean;

  // 토스트
  toasts: Toast[];

  // SSE 연결 상태
  isConnected: boolean;

  // 알림 액션
  markAsRead: (id: string) => Promise<void>;
  markAllAsRead: () => Promise<void>;
  dismiss: (id: string) => Promise<void>;
  refreshNotifications: () => Promise<void>;

  // 토스트 액션
  addToast: (toast: Omit<Toast, "id">) => void;
  removeToast: (id: string) => void;
}

const NotificationContext = createContext<NotificationContextType | null>(null);

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function NotificationProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated, accessToken } = useAuth();

  // 알림 상태
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [isConnected, setIsConnected] = useState(false);

  // 토스트 상태
  const [toasts, setToasts] = useState<Toast[]>([]);

  // SSE EventSource 참조
  const eventSourceRef = useRef<EventSource | null>(null);

  // 알림 목록 새로고침
  const refreshNotifications = useCallback(async () => {
    if (!isAuthenticated) return;

    setIsLoading(true);
    try {
      const response = await notificationsApi.list({ page: 1, size: 20 });
      setNotifications(response.data.items);
      setUnreadCount(response.data.unread_count);
    } catch (error) {
      console.error("Failed to fetch notifications:", error);
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  // 읽음 처리
  const markAsRead = useCallback(async (id: string) => {
    try {
      await notificationsApi.markAsRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch (error) {
      console.error("Failed to mark notification as read:", error);
    }
  }, []);

  // 전체 읽음
  const markAllAsRead = useCallback(async () => {
    try {
      await notificationsApi.markAllAsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch (error) {
      console.error("Failed to mark all as read:", error);
    }
  }, []);

  // 숨기기
  const dismiss = useCallback(async (id: string) => {
    try {
      await notificationsApi.dismiss(id);
      const notification = notifications.find((n) => n.id === id);
      setNotifications((prev) => prev.filter((n) => n.id !== id));
      if (notification && !notification.is_read) {
        setUnreadCount((prev) => Math.max(0, prev - 1));
      }
    } catch (error) {
      console.error("Failed to dismiss notification:", error);
    }
  }, [notifications]);

  // 토스트 추가
  const addToast = useCallback((toast: Omit<Toast, "id">) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const newToast: Toast = { ...toast, id };

    setToasts((prev) => [...prev, newToast]);

    // 자동 제거 (기본 5초)
    if (toast.duration !== undefined && toast.duration > 0) {
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, toast.duration);
    } else if (toast.duration === undefined) {
      // 기본 5초
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 5000);
    }
  }, []);

  // 토스트 제거
  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // SSE 연결 설정
  useEffect(() => {
    if (!isAuthenticated || !accessToken) {
      // 연결 해제
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
        setIsConnected(false);
      }
      return;
    }

    // 초기 알림 로드
    refreshNotifications();

    // 재시도 카운터
    let retryCount = 0;
    const maxRetries = 3;
    let retryTimeout: NodeJS.Timeout | null = null;

    // SSE 연결
    const connectSSE = () => {
      const url = `${API_BASE_URL}/notifications/stream`;
      const token = localStorage.getItem("access_token");

      // 토큰이 없으면 SSE 연결하지 않음
      if (!token) {
        console.warn("No access token available for SSE connection");
        return;
      }

      // 이미 연결 중이거나 연결된 상태면 스킵
      if (eventSourceRef.current?.readyState === EventSource.OPEN) {
        return;
      }

      console.log(`SSE connecting... (attempt ${retryCount + 1}/${maxRetries})`);

      const eventSource = new EventSource(
        `${url}?token=${encodeURIComponent(token)}`
      );

      eventSource.onopen = () => {
        setIsConnected(true);
        retryCount = 0; // 성공 시 리셋
        console.log("Notification SSE connected");
      };

      eventSource.onerror = () => {
        const readyState = eventSource.readyState;
        setIsConnected(false);
        eventSource.close();

        // 토큰이 만료되었을 수 있으므로 localStorage 확인
        const currentToken = localStorage.getItem("access_token");
        if (!currentToken) {
          console.warn("Token removed, not reconnecting SSE");
          return;
        }

        // 최대 재시도 횟수 체크
        if (retryCount >= maxRetries) {
          console.warn(`SSE connection failed after ${maxRetries} attempts, giving up`);
          return;
        }

        retryCount++;
        const delay = Math.min(1000 * Math.pow(2, retryCount), 30000); // exponential backoff, max 30s
        console.log(`SSE reconnecting in ${delay}ms... (readyState was ${readyState})`);

        retryTimeout = setTimeout(() => {
          if (isAuthenticated) {
            connectSSE();
          }
        }, delay);
      };

      // 새 알림 이벤트
      eventSource.addEventListener("notification", (event) => {
        try {
          const data = JSON.parse(event.data);
          const notification: NotificationItem = {
            id: data.id,
            type: data.type,
            category: data.category || "agent",
            title: data.title,
            message: data.message,
            priority: data.priority || "normal",
            icon: data.icon,
            entity_type: data.entity_type,
            entity_id: data.entity_id,
            action_type: data.action_type,
            action_url: data.action_url,
            is_read: false,
            created_at: new Date().toISOString(),
          };

          // 알림 목록에 추가
          setNotifications((prev) => [notification, ...prev]);
          setUnreadCount((prev) => prev + 1);

          // 토스트 표시
          addToast({
            type: getToastType(notification.type),
            title: notification.title,
            message: notification.message,
            duration: 5000,
            action: notification.action_url
              ? {
                  label: "보기",
                  onClick: () => {
                    window.location.href = notification.action_url!;
                  },
                }
              : undefined,
          });
        } catch (error) {
          console.error("Failed to parse notification event:", error);
        }
      });

      // 읽지 않은 수 업데이트 이벤트
      eventSource.addEventListener("unread_count", (event) => {
        try {
          const data = JSON.parse(event.data);
          setUnreadCount(data.count);
        } catch (error) {
          console.error("Failed to parse unread_count event:", error);
        }
      });

      // 하트비트
      eventSource.addEventListener("heartbeat", () => {
        // 연결 유지 확인
      });

      eventSourceRef.current = eventSource;
    };

    connectSSE();

    return () => {
      // 재시도 타이머 정리
      if (retryTimeout) {
        clearTimeout(retryTimeout);
      }
      // SSE 연결 종료
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
        setIsConnected(false);
      }
    };
  }, [isAuthenticated, accessToken, refreshNotifications, addToast]);

  return (
    <NotificationContext.Provider
      value={{
        notifications,
        unreadCount,
        isLoading,
        toasts,
        isConnected,
        markAsRead,
        markAllAsRead,
        dismiss,
        refreshNotifications,
        addToast,
        removeToast,
      }}
    >
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotifications() {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error(
      "useNotifications must be used within a NotificationProvider"
    );
  }
  return context;
}

// 알림 타입에 따른 토스트 타입 결정
function getToastType(
  notificationType: string
): "info" | "success" | "warning" | "error" {
  switch (notificationType) {
    case "job_completed":
      return "success";
    case "job_failed":
      return "error";
    case "job_waiting_approval":
      return "warning";
    default:
      return "info";
  }
}

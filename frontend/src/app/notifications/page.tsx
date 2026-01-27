"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import {
  Bell,
  ArrowLeft,
  Check,
  CheckCheck,
  Trash2,
  Search,
  Bot,
  MessageSquare,
  BarChart3,
  Loader2,
  Play,
  CheckCircle,
  Clock,
  XCircle,
  Info,
  Filter,
} from "lucide-react";
import { useNotifications } from "@/contexts/NotificationContext";
import { NotificationItem, notificationsApi, PaginatedNotifications } from "@/lib/api";

type FilterType = "all" | "unread" | "agent" | "system";

export default function NotificationsPage() {
  const router = useRouter();
  const {
    notifications: recentNotifications,
    unreadCount,
    isLoading: contextLoading,
    markAsRead,
    markAllAsRead,
    dismiss,
    refreshNotifications,
  } = useNotifications();

  // Full list with pagination
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [pagination, setPagination] = useState({
    page: 1,
    size: 20,
    total: 0,
    pages: 1,
  });
  const [filter, setFilter] = useState<FilterType>("all");

  // Fetch notifications with pagination
  const fetchNotifications = useCallback(async (page: number = 1, currentFilter: FilterType = filter) => {
    setLoading(true);
    try {
      const params: { page: number; size: number; is_read?: boolean; category?: string } = {
        page,
        size: pagination.size,
      };

      if (currentFilter === "unread") {
        params.is_read = false;
      } else if (currentFilter === "agent") {
        params.category = "agent";
      } else if (currentFilter === "system") {
        params.category = "system";
      }

      const response = await notificationsApi.list(params);
      const data: PaginatedNotifications = response.data;

      setNotifications(data.items);
      setPagination({
        page: data.page,
        size: data.size,
        total: data.total,
        pages: data.pages,
      });
    } catch (error) {
      console.error("Failed to fetch notifications:", error);
    } finally {
      setLoading(false);
    }
  }, [filter, pagination.size]);

  useEffect(() => {
    fetchNotifications();
  }, []);

  // Handle filter change
  const handleFilterChange = (newFilter: FilterType) => {
    setFilter(newFilter);
    fetchNotifications(1, newFilter);
  };

  // Handle notification click
  const handleClick = async (notification: NotificationItem) => {
    if (!notification.is_read) {
      await markAsRead(notification.id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === notification.id ? { ...n, is_read: true } : n))
      );
    }

    if (notification.action_url) {
      router.push(notification.action_url);
      return;
    }

    // Fallback navigation based on entity type
    if (notification.entity_type === "agent_job" && notification.entity_id) {
      if (notification.type === "approval_required" || notification.action_type === "approve") {
        router.push(`/agents/study-plan/jobs/${notification.entity_id}`);
        return;
      }
      router.push(`/agents/study-plan/history`);
    }
  };

  // Handle dismiss
  const handleDismiss = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    await dismiss(id);
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  };

  // Handle mark all as read
  const handleMarkAllAsRead = async () => {
    await markAllAsRead();
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
  };

  // Format time
  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();

    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return "방금 전";
    if (minutes < 60) return `${minutes}분 전`;
    if (hours < 24) return `${hours}시간 전`;
    if (days < 7) return `${days}일 전`;
    return date.toLocaleDateString("ko-KR", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  };

  // Get icon by notification type
  const getIcon = (type: string) => {
    switch (type) {
      case "job_started":
        return (
          <div className="w-10 h-10 rounded-full bg-blue-100 dark:bg-blue-900 flex items-center justify-center flex-shrink-0">
            <Play size={18} className="text-blue-600 dark:text-blue-400" />
          </div>
        );
      case "job_completed":
        return (
          <div className="w-10 h-10 rounded-full bg-green-100 dark:bg-green-900 flex items-center justify-center flex-shrink-0">
            <CheckCircle size={18} className="text-green-600 dark:text-green-400" />
          </div>
        );
      case "job_waiting_approval":
      case "approval_required":
        return (
          <div className="w-10 h-10 rounded-full bg-yellow-100 dark:bg-yellow-900 flex items-center justify-center flex-shrink-0">
            <Clock size={18} className="text-yellow-600 dark:text-yellow-400" />
          </div>
        );
      case "job_failed":
        return (
          <div className="w-10 h-10 rounded-full bg-red-100 dark:bg-red-900 flex items-center justify-center flex-shrink-0">
            <XCircle size={18} className="text-red-600 dark:text-red-400" />
          </div>
        );
      default:
        return (
          <div className="w-10 h-10 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center flex-shrink-0">
            <Info size={18} className="text-gray-600 dark:text-gray-400" />
          </div>
        );
    }
  };

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header with Tabs - Fixed */}
      <div className="bg-[var(--background)]">
        <div className="flex items-center justify-center">
          <div className="flex items-center gap-6">
            <Link
              href="/ask"
              className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-colors"
            >
              <MessageSquare size={20} />
              Ask AI
            </Link>
            <Link
              href="/main"
              className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-colors"
            >
              <Search size={20} />
              Search Papers
            </Link>
            <Link
              href="/agents"
              className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-colors"
            >
              <Bot size={20} />
              Agents
            </Link>
            <Link
              href="/dashboard"
              className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-colors"
            >
              <BarChart3 size={20} />
              Dashboard
            </Link>
          </div>
        </div>
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-6 py-8">
          {/* Back Link & Title */}
          <div className="mb-8">
            <button
              type="button"
              onClick={() => router.back()}
              className="inline-flex items-center gap-1 text-sm text-[var(--oaria-text-secondary)] hover:text-[var(--oaria-teal)] transition-colors mb-4"
            >
              <ArrowLeft size={16} />
              뒤로 가기
            </button>

            <div className="flex items-center justify-between">
              <div>
                <h1 className="font-[family-name:var(--font-outfit)] text-2xl font-semibold flex items-center gap-3">
                  <Bell size={24} className="text-[var(--oaria-teal)]" />
                  알림
                  {unreadCount > 0 && (
                    <span className="text-sm font-normal text-[var(--oaria-text-secondary)]">
                      ({unreadCount}개 읽지 않음)
                    </span>
                  )}
                </h1>
                <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] mt-1">
                  에이전트 작업 상태, 승인 요청 등 알림을 확인할 수 있습니다.
                </p>
              </div>

              {unreadCount > 0 && (
                <button
                  type="button"
                  onClick={handleMarkAllAsRead}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--oaria-teal)] text-white text-sm font-medium hover:bg-[var(--oaria-teal)]/80 transition-colors"
                >
                  <CheckCheck size={16} />
                  모두 읽음
                </button>
              )}
            </div>

            {/* Filter Tabs */}
            <div className="flex items-center gap-2 mt-6">
              <Filter size={16} className="text-[var(--oaria-text-secondary)]" />
              <div className="flex gap-1">
                {[
                  { key: "all", label: "전체" },
                  { key: "unread", label: "읽지 않음" },
                  { key: "agent", label: "에이전트" },
                  { key: "system", label: "시스템" },
                ].map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => handleFilterChange(item.key as FilterType)}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                      filter === item.key
                        ? "bg-[var(--oaria-teal)] text-white"
                        : "bg-[var(--oaria-border)] hover:bg-[var(--oaria-border)]/80"
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Loading */}
          {loading && (
            <div className="flex items-center justify-center py-16">
              <Loader2 size={32} className="animate-spin text-[var(--oaria-teal)]" />
            </div>
          )}

          {/* Empty State */}
          {!loading && notifications.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="w-16 h-16 rounded-full bg-[var(--oaria-teal)]/10 flex items-center justify-center mb-4">
                <Bell size={28} className="text-[var(--oaria-teal)]" />
              </div>
              <h3 className="font-[family-name:var(--font-outfit)] text-lg font-semibold mb-2">
                {filter === "unread" ? "읽지 않은 알림이 없습니다" : "알림이 없습니다"}
              </h3>
              <p className="text-sm text-[var(--oaria-text-secondary)]">
                {filter === "unread"
                  ? "모든 알림을 확인했습니다."
                  : "새로운 알림이 오면 여기에 표시됩니다."}
              </p>
            </div>
          )}

          {/* Notification List */}
          {!loading && notifications.length > 0 && (
            <>
              <div className="space-y-2">
                {notifications.map((notification) => (
                  <div
                    key={notification.id}
                    onClick={() => handleClick(notification)}
                    className={`
                      p-4 rounded-xl border-2 cursor-pointer transition-all
                      ${
                        !notification.is_read
                          ? "border-[var(--oaria-teal)]/30 bg-[var(--oaria-teal)]/5"
                          : "border-[var(--oaria-border)] bg-[var(--background)] hover:border-[var(--oaria-teal)]/20"
                      }
                    `}
                  >
                    <div className="flex gap-4">
                      {/* Icon */}
                      {getIcon(notification.type)}

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              {!notification.is_read && (
                                <span className="w-2 h-2 rounded-full bg-[var(--oaria-teal)]" />
                              )}
                              <p
                                className={`text-sm truncate ${
                                  !notification.is_read ? "font-semibold" : ""
                                }`}
                              >
                                {notification.title}
                              </p>
                            </div>
                            <p className="text-sm text-[var(--oaria-text-secondary)] line-clamp-2">
                              {notification.message}
                            </p>
                            <p className="text-xs text-[var(--oaria-text-secondary)] mt-2">
                              {formatTime(notification.created_at)}
                            </p>
                          </div>

                          {/* Actions */}
                          <div className="flex items-center gap-1 flex-shrink-0">
                            {!notification.is_read && (
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  markAsRead(notification.id);
                                  setNotifications((prev) =>
                                    prev.map((n) =>
                                      n.id === notification.id
                                        ? { ...n, is_read: true }
                                        : n
                                    )
                                  );
                                }}
                                className="p-2 rounded-lg hover:bg-[var(--oaria-border)] text-[var(--oaria-text-secondary)] hover:text-[var(--oaria-teal)] transition-colors"
                                title="읽음 처리"
                              >
                                <Check size={16} />
                              </button>
                            )}
                            <button
                              type="button"
                              onClick={(e) => handleDismiss(e, notification.id)}
                              className="p-2 rounded-lg hover:bg-[var(--oaria-border)] text-[var(--oaria-text-secondary)] hover:text-red-500 transition-colors"
                              title="삭제"
                            >
                              <Trash2 size={16} />
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Pagination */}
              {pagination.pages > 1 && (
                <div className="flex items-center justify-center gap-4 mt-8">
                  <button
                    type="button"
                    onClick={() => fetchNotifications(pagination.page - 1)}
                    disabled={pagination.page <= 1}
                    className="px-4 py-2 rounded-lg border border-[var(--oaria-border)] disabled:opacity-50 disabled:cursor-not-allowed hover:border-[var(--oaria-teal)] transition-colors text-sm font-medium"
                  >
                    이전
                  </button>
                  <span className="text-sm text-[var(--oaria-text-secondary)]">
                    {pagination.page} / {pagination.pages} 페이지
                  </span>
                  <button
                    type="button"
                    onClick={() => fetchNotifications(pagination.page + 1)}
                    disabled={pagination.page >= pagination.pages}
                    className="px-4 py-2 rounded-lg border border-[var(--oaria-border)] disabled:opacity-50 disabled:cursor-not-allowed hover:border-[var(--oaria-teal)] transition-colors text-sm font-medium"
                  >
                    다음
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

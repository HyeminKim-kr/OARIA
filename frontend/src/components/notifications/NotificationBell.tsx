"use client";

import { useState, useRef, useEffect } from "react";
import { useNotifications } from "@/contexts/NotificationContext";
import { NotificationCenter } from "./NotificationCenter";

export function NotificationBell() {
  const { unreadCount, isConnected } = useNotifications();
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // 외부 클릭 시 닫기
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div ref={containerRef} className="relative">
      {/* 벨 버튼 */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`
          relative p-2 rounded-lg
          text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100
          hover:bg-gray-100 dark:hover:bg-gray-800
          transition-colors
        `}
        title={`알림 ${unreadCount > 0 ? `(${unreadCount}개 읽지 않음)` : ""}`}
      >
        {/* 벨 아이콘 */}
        <svg
          className="w-6 h-6"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
          />
        </svg>

        {/* 읽지 않은 알림 배지 */}
        {unreadCount > 0 && (
          <span
            className={`
              absolute -top-1 -right-1
              min-w-[20px] h-5 px-1
              flex items-center justify-center
              text-xs font-bold text-white
              bg-red-500 rounded-full
              ${unreadCount > 9 ? "text-[10px]" : ""}
            `}
          >
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}

        {/* 연결 상태 표시 */}
        {isConnected && (
          <span className="absolute bottom-1 right-1 w-2 h-2 bg-green-500 rounded-full" />
        )}
      </button>

      {/* 알림 센터 패널 */}
      {isOpen && (
        <div
          className={`
            absolute right-0 mt-2 w-80 sm:w-96
            bg-white dark:bg-gray-900
            rounded-lg shadow-xl
            border border-gray-200 dark:border-gray-700
            z-50
          `}
        >
          <NotificationCenter onClose={() => setIsOpen(false)} />
        </div>
      )}
    </div>
  );
}

"use client";

import { useState } from "react";
import { Plus, MessageSquare, MoreHorizontal, Pencil, Trash2 } from "lucide-react";

interface Conversation {
  id: string;
  title: string;
  updatedAt: Date;
}

// 임시 대화 히스토리 데이터
const mockConversations: Conversation[] = [
  { id: "1", title: "폐암 면역치료 최신 연구", updatedAt: new Date("2025-12-28") },
  { id: "2", title: "CAR-T 세포치료 고형암 적용", updatedAt: new Date("2025-12-27") },
  { id: "3", title: "PD-1과 PD-L1 억제제 비교", updatedAt: new Date("2025-12-26") },
  { id: "4", title: "액체 생검 조기 진단", updatedAt: new Date("2025-12-25") },
  { id: "5", title: "종양 미세환경 분석", updatedAt: new Date("2025-12-24") },
];

interface ChatSidebarProps {
  currentConversationId?: string;
  onNewChat: () => void;
  onSelectConversation: (id: string) => void;
}

export function ChatSidebar({
  currentConversationId,
  onNewChat,
  onSelectConversation,
}: ChatSidebarProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  return (
    <aside className="hidden lg:flex fixed left-0 top-16 bottom-0 w-64 bg-[var(--oaria-border)]/20 border-r-2 border-[var(--oaria-border-strong)] flex-col z-40">
      {/* New Chat Button */}
      <div className="p-3">
        <button
          onClick={onNewChat}
          className="w-full flex items-center gap-3 px-4 py-3 rounded-xl border-2 border-[var(--oaria-border-strong)] hover:bg-[var(--background)] transition-colors text-[var(--foreground)]"
        >
          <Plus size={18} />
          <span className="font-[family-name:var(--font-dm-sans)] text-sm font-medium">
            새 대화
          </span>
        </button>
      </div>

      {/* Conversation List */}
      <div className="flex-1 overflow-y-auto px-3 pb-3">
        <div className="space-y-1">
          {mockConversations.map((conversation) => {
            const isActive = conversation.id === currentConversationId;
            const isHovered = conversation.id === hoveredId;

            return (
              <div
                key={conversation.id}
                className={`group relative flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer transition-colors ${
                  isActive
                    ? "bg-[var(--oaria-teal)]/10 text-[var(--oaria-teal)]"
                    : "hover:bg-[var(--background)] text-[var(--foreground)]"
                }`}
                onMouseEnter={() => setHoveredId(conversation.id)}
                onMouseLeave={() => setHoveredId(null)}
                onClick={() => onSelectConversation(conversation.id)}
              >
                <MessageSquare size={16} className="flex-shrink-0" />
                <span className="flex-1 font-[family-name:var(--font-dm-sans)] text-sm truncate">
                  {conversation.title}
                </span>

                {/* Action Buttons - Show on hover */}
                {isHovered && (
                  <div className="flex items-center gap-1">
                    <button
                      className="p-1 rounded hover:bg-[var(--oaria-border)] transition-colors"
                      onClick={(e) => {
                        e.stopPropagation();
                        // TODO: Rename
                      }}
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      className="p-1 rounded hover:bg-[var(--oaria-border)] text-[var(--oaria-coral)] transition-colors"
                      onClick={(e) => {
                        e.stopPropagation();
                        // TODO: Delete
                      }}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </aside>
  );
}

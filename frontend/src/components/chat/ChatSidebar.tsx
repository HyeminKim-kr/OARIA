"use client";

import { useState, useEffect } from "react";
import { Plus, MessageSquare, Pencil, Trash2, Loader2, Check, X } from "lucide-react";
import { conversationsApi, ConversationListItem } from "@/lib/api";

interface ChatSidebarProps {
  currentConversationId?: string;
  onNewChat: () => void;
  onSelectConversation: (id: string) => void;
  refreshTrigger?: number; // 외부에서 리프레시 트리거
}

export function ChatSidebar({
  currentConversationId,
  onNewChat,
  onSelectConversation,
  refreshTrigger,
}: ChatSidebarProps) {
  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");

  // 대화 목록 로드
  const loadConversations = async () => {
    try {
      const response = await conversationsApi.list(1, 50);
      setConversations(response.data.items);
    } catch (error) {
      console.error("Failed to load conversations:", error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadConversations();
  }, [refreshTrigger]);

  // 대화 삭제
  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("이 대화를 삭제하시겠습니까?")) return;

    try {
      await conversationsApi.delete(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (currentConversationId === id) {
        onNewChat();
      }
    } catch (error) {
      console.error("Failed to delete conversation:", error);
    }
  };

  // 대화 제목 수정 시작
  const handleEditStart = (conversation: ConversationListItem, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(conversation.id);
    setEditTitle(conversation.title || "");
  };

  // 대화 제목 수정 저장
  const handleEditSave = async (id: string) => {
    if (!editTitle.trim()) {
      setEditingId(null);
      return;
    }

    try {
      await conversationsApi.update(id, { title: editTitle.trim() });
      setConversations((prev) =>
        prev.map((c) => (c.id === id ? { ...c, title: editTitle.trim() } : c))
      );
    } catch (error) {
      console.error("Failed to update conversation:", error);
    } finally {
      setEditingId(null);
    }
  };

  // 대화 제목 수정 취소
  const handleEditCancel = () => {
    setEditingId(null);
    setEditTitle("");
  };

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
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 size={24} className="animate-spin text-[var(--oaria-teal)]" />
          </div>
        ) : conversations.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-sm text-[var(--oaria-text-secondary)]">
              대화 내역이 없습니다
            </p>
          </div>
        ) : (
          <div className="space-y-1">
            {conversations.map((conversation) => {
              const isActive = conversation.id === currentConversationId;
              const isHovered = conversation.id === hoveredId;
              const isEditing = conversation.id === editingId;

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
                  onClick={() => !isEditing && onSelectConversation(conversation.id)}
                >
                  <MessageSquare size={16} className="flex-shrink-0" />

                  {isEditing ? (
                    <div className="flex-1 flex items-center gap-1">
                      <input
                        type="text"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        onClick={(e) => e.stopPropagation()}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handleEditSave(conversation.id);
                          if (e.key === "Escape") handleEditCancel();
                        }}
                        className="flex-1 px-2 py-1 text-sm bg-[var(--background)] border border-[var(--oaria-border)] rounded focus:outline-none focus:border-[var(--oaria-teal)]"
                        autoFocus
                      />
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleEditSave(conversation.id);
                        }}
                        className="p-1 rounded hover:bg-[var(--oaria-teal)]/20 text-[var(--oaria-teal)]"
                      >
                        <Check size={14} />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleEditCancel();
                        }}
                        className="p-1 rounded hover:bg-[var(--oaria-border)]"
                      >
                        <X size={14} />
                      </button>
                    </div>
                  ) : (
                    <>
                      <span className="flex-1 font-[family-name:var(--font-dm-sans)] text-sm truncate">
                        {conversation.title || "새 대화"}
                      </span>

                      {/* Action Buttons - Show on hover */}
                      {isHovered && (
                        <div className="flex items-center gap-1">
                          <button
                            className="p-1 rounded hover:bg-[var(--oaria-border)] transition-colors"
                            onClick={(e) => handleEditStart(conversation, e)}
                          >
                            <Pencil size={14} />
                          </button>
                          <button
                            className="p-1 rounded hover:bg-[var(--oaria-border)] text-[var(--oaria-coral)] transition-colors"
                            onClick={(e) => handleDelete(conversation.id, e)}
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      )}
                    </>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </aside>
  );
}

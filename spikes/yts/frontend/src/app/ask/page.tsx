"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import {
  ArrowUp,
  Search,
  Bot,
  FileText,
  ExternalLink,
  Loader2,
  MessageSquare,
} from "lucide-react";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { ReferenceModal } from "@/components/chat/ReferenceModal";
import { fetchWithAuth } from "@/lib/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Reference {
  paper_id: string;
  chunk_id: string;
  title: string;
  journal: string;
  year: number;
  section: string;
  snippet: string;
  offset_start: number;
  offset_end: number;
  distance: number;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  references?: Reference[];
}

export default function AskPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [currentConversationId, setCurrentConversationId] = useState<string | undefined>();
  const [selectedReference, setSelectedReference] = useState<Reference | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const handleNewChat = () => {
    setMessages([]);
    setCurrentConversationId(undefined);
  };

  const handleSelectConversation = (id: string) => {
    setCurrentConversationId(id);
    // TODO: Load conversation messages
    setMessages([]);
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const question = input;
    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: question,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    // Assistant 메시지 placeholder 추가
    const assistantMessageId = (Date.now() + 1).toString();
    setMessages((prev) => [
      ...prev,
      {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        references: [],
      },
    ]);

    try {
      const response = await fetchWithAuth(`${API_BASE_URL}/ai/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question,
          conversation_id: currentConversationId,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error("No response body");
      }

      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            // SSE event type (references, token, done) - data에서 처리
            continue;
          }

          if (line.startsWith("data: ")) {
            const dataStr = line.slice(6);
            try {
              const data = JSON.parse(dataStr);

              // status 이벤트 (진행 상태)
              if (data.step && data.message) {
                setStatusMessage(data.message);
              }

              // references 이벤트
              if (data.references) {
                setStatusMessage(""); // 상태 메시지 초기화
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMessageId
                      ? { ...msg, references: data.references }
                      : msg
                  )
                );
              }

              // token 이벤트
              if (data.token) {
                setStatusMessage(""); // 상태 메시지 초기화
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMessageId
                      ? { ...msg, content: msg.content + data.token }
                      : msg
                  )
                );
              }

              // done 이벤트
              if (data.conversation_id) {
                setCurrentConversationId(data.conversation_id);
              }
            } catch {
              // JSON 파싱 실패 시 무시
            }
          }
        }
      }
    } catch (error) {
      console.error("Ask AI error:", error);
      // 에러 시 에러 메시지 표시
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId
            ? {
                ...msg,
                content: "죄송합니다. 응답을 생성하는 중 오류가 발생했습니다. 다시 시도해주세요.",
              }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
      setStatusMessage("");
    }
  };

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Chat History Sidebar - Fixed in left margin */}
      <ChatSidebar
        currentConversationId={currentConversationId}
        onNewChat={handleNewChat}
        onSelectConversation={handleSelectConversation}
      />

      {/* Main Content Area - offset by sidebar width on large screens */}
      <div className="h-full flex flex-col lg:ml-64">
        {/* Header with Toggle */}
        <div className="bg-[var(--background)]">
          <div className="flex items-center justify-center py-4">
          {/* Ask/Search Toggle */}
          <div className="inline-flex items-center bg-[var(--oaria-border)]/50 rounded-full p-1">
            <button
              type="button"
              className="flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium bg-[var(--oaria-teal)] text-white shadow-sm"
            >
              <MessageSquare size={16} />
              Ask AI
            </button>
            <Link
              href="/main"
              className="flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-all"
            >
              <Search size={16} />
              Search Papers
            </Link>
          </div>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto px-6 py-8">
          {messages.length === 0 ? (
            // Empty State
            <div className="flex flex-col items-center justify-center min-h-[400px]">
              <div className="w-16 h-16 rounded-full bg-[var(--oaria-teal)]/10 flex items-center justify-center mb-6">
                <Bot size={32} className="text-[var(--oaria-teal)]" />
              </div>
              <h2 className="font-[family-name:var(--font-outfit)] text-3xl font-semibold text-center mb-2">
                Ask about research
              </h2>
              <p className="font-[family-name:var(--font-dm-sans)] text-base text-[var(--oaria-text-secondary)] text-center max-w-md mb-8">
                Get AI-powered answers based on research papers. Your questions
                will be answered with relevant citations.
              </p>
              <div className="flex flex-wrap gap-2 justify-center">
                {[
                  "What are the latest advances in lung cancer immunotherapy?",
                  "Explain CAR-T cell therapy for solid tumors",
                  "Compare PD-1 and PD-L1 inhibitors",
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => setInput(suggestion)}
                    className="px-4 py-2 rounded-full border border-[var(--oaria-border)] text-sm text-[var(--oaria-text-secondary)] hover:border-[var(--oaria-teal)] hover:text-[var(--oaria-teal)] transition-colors"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            // Messages
            <div className="space-y-6">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex gap-3 w-full ${message.role === "user" ? "justify-end" : ""}`}
                >
                  {/* AI Avatar - Left side */}
                  {message.role === "assistant" && (
                    <div className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center bg-[var(--oaria-teal)]">
                      <Bot size={16} className="text-white" />
                    </div>
                  )}

                  {/* Content */}
                  <div
                    className={`${
                      message.role === "user"
                        ? "max-w-[70%] bg-[var(--oaria-teal)] text-white rounded-2xl rounded-br-md px-4 py-3"
                        : "flex-1"
                    }`}
                  >
                    {message.role === "assistant" && (
                      <div className="font-[family-name:var(--font-dm-sans)] text-base mb-1 text-[var(--oaria-text-secondary)]">
                        AI Assistant
                      </div>
                    )}
                    <div
                      className={`font-[family-name:var(--font-dm-sans)] text-base whitespace-pre-wrap leading-relaxed ${
                        message.role === "user" ? "" : "text-[var(--foreground)]"
                      }`}
                    >
                      {message.content}
                      {/* 스트리밍 중 커서 표시 */}
                      {isLoading && message.role === "assistant" && message.id === messages[messages.length - 1]?.id && message.content && (
                        <span className="inline-block w-2 h-5 bg-[var(--oaria-teal)] ml-1 animate-pulse" />
                      )}
                    </div>

                    {/* References */}
                    {message.references && message.references.length > 0 && (
                      <div className="mt-6 pt-4 border-t border-[var(--oaria-border)]">
                        <div className="flex items-center gap-2 mb-3">
                          <FileText
                            size={16}
                            className="text-[var(--oaria-teal)]"
                          />
                          <span className="font-[family-name:var(--font-outfit)] text-sm font-medium">
                            References
                          </span>
                        </div>
                        <div className="space-y-3">
                          {message.references.map((ref, idx) => (
                            <div
                              key={`${ref.paper_id}-${ref.section}-${idx}`}
                              className="p-4 rounded-lg bg-[var(--oaria-border)]/20 hover:bg-[var(--oaria-border)]/40 transition-colors group cursor-pointer"
                              onClick={() => setSelectedReference(ref)}
                            >
                              <div className="flex items-start gap-3">
                                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-[var(--oaria-teal)]/20 text-[var(--oaria-teal)] text-xs font-medium flex items-center justify-center">
                                  {idx + 1}
                                </span>
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-start justify-between gap-2">
                                    <div className="font-[family-name:var(--font-dm-sans)] text-sm font-medium text-[var(--foreground)] group-hover:text-[var(--oaria-teal)] transition-colors">
                                      {ref.title}
                                    </div>
                                    <ExternalLink
                                      size={14}
                                      className="flex-shrink-0 text-[var(--oaria-text-secondary)] opacity-0 group-hover:opacity-100 transition-opacity mt-0.5"
                                    />
                                  </div>
                                  <div className="font-[family-name:var(--font-dm-sans)] text-xs text-[var(--oaria-tagline)] mt-1">
                                    {ref.journal} ({ref.year}) · {ref.section}
                                  </div>
                                  {/* 근거 텍스트 (snippet) */}
                                  <div className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] mt-2 line-clamp-3 leading-relaxed">
                                    {ref.snippet}
                                  </div>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {/* Loading Indicator - 상태 메시지 표시 */}
              {isLoading && statusMessage && (
                <div className="flex items-center gap-2 text-[var(--oaria-text-secondary)] ml-11">
                  <Loader2 size={18} className="animate-spin text-[var(--oaria-teal)]" />
                  <span className="font-[family-name:var(--font-dm-sans)] text-base">
                    {statusMessage}
                  </span>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>
      </div>

      {/* Input Area - Fixed at bottom */}
      <div className="border-t-2 border-[var(--oaria-border-strong)] bg-[var(--background)]">
        <div className="max-w-5xl mx-auto px-6 py-4">
          <form onSubmit={handleSubmit}>
            <div className="relative bg-[var(--background)] border-2 border-[var(--oaria-border-strong)] rounded-2xl hover:border-[var(--oaria-teal)]/50 focus-within:border-[var(--oaria-teal)] focus-within:ring-2 focus-within:ring-[var(--oaria-teal)]/20 transition-all">
              <div className="flex items-center px-4 py-3">
                <MessageSquare size={20} className="text-[var(--oaria-teal)] mr-3" />
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask about research..."
                  disabled={isLoading}
                  className="flex-1 bg-transparent font-[family-name:var(--font-dm-sans)] text-base outline-none placeholder:text-[var(--oaria-tagline)] disabled:opacity-50"
                />
                <button
                  type="submit"
                  disabled={!input.trim() || isLoading}
                  className="w-10 h-10 rounded-full bg-[var(--oaria-teal)] hover:bg-[var(--oaria-light-teal)] disabled:bg-[var(--oaria-border)] disabled:cursor-not-allowed flex items-center justify-center transition-colors ml-2"
                >
                  {isLoading ? (
                    <Loader2 size={20} className="text-white animate-spin" />
                  ) : (
                    <ArrowUp size={20} className="text-white" />
                  )}
                </button>
              </div>
            </div>
          </form>
          <p className="font-[family-name:var(--font-dm-sans)] text-xs text-center text-[var(--oaria-tagline)] mt-2">
            AI answers are based on indexed research papers. Always verify with
            original sources.
          </p>
        </div>
      </div>
      </div>

      {/* Reference Modal */}
      {selectedReference && (
        <ReferenceModal
          reference={selectedReference}
          onClose={() => setSelectedReference(null)}
        />
      )}
    </div>
  );
}

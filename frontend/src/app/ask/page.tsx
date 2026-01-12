"use client";

import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
import {
  ArrowUp,
  Search,
  Bot,
  FileText,
  ExternalLink,
  Loader2,
  MessageSquare,
  Lightbulb,
  ChevronDown,
  ChevronRight,
  Copy,
  Check,
  AlertTriangle,
} from "lucide-react";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { ReferenceModal } from "@/components/chat/ReferenceModal";
import { fetchWithAuth, conversationsApi } from "@/lib/api";

// 추천 질문 파싱 헬퍼
function parseSuggestions(content: string): { mainContent: string; suggestions: string[] } {
  const suggestionsMatch = content.match(/```suggestions\n([\s\S]*?)```/);
  if (!suggestionsMatch) {
    return { mainContent: content, suggestions: [] };
  }

  const mainContent = content.replace(/### 5\. 추천 질문[\s\S]*```suggestions[\s\S]*?```/, "").trim();
  const suggestions = suggestionsMatch[1]
    .split("\n")
    .filter((line) => line.startsWith("- "))
    .map((line) => line.slice(2).trim());

  return { mainContent, suggestions };
}

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

interface SubTask {
  id: string;
  query: string;
  tool: string;
  depends_on: string[];
  status?: "pending" | "running" | "completed";
}

interface AgentProgress {
  complexity?: {
    level: string;
    reasoning: string;
  };
  subtasks?: SubTask[];
}

interface GateClassification {
  category: string;
  confidence: number;
  is_oncology: boolean;
  warning: string | null;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  references?: Reference[];
}

export default function AskPage() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [currentConversationId, setCurrentConversationId] = useState<string | undefined>();
  const [selectedReference, setSelectedReference] = useState<Reference | null>(null);
  const [sidebarRefresh, setSidebarRefresh] = useState(0);
  const [agentProgress, setAgentProgress] = useState<AgentProgress | null>(null);
  const [gateClassification, setGateClassification] = useState<GateClassification | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // URL에서 conversation ID 읽어서 메시지 로드
  const loadConversation = useCallback(async (id: string) => {
    setCurrentConversationId(id);
    setIsLoadingMessages(true);
    setMessages([]);

    try {
      const response = await conversationsApi.getMessages(id);
      const loadedMessages: Message[] = response.data.items.map((m) => ({
        id: m.id,
        role: m.role as "user" | "assistant",
        content: m.content,
        references: m.references?.map((r) => ({
          paper_id: r.paper_id,
          chunk_id: r.chunk_id,
          title: r.title,
          journal: r.journal || "",
          year: r.year || 0,
          section: r.section,
          snippet: r.snippet,
          offset_start: r.offset_start,
          offset_end: r.offset_end,
          distance: r.distance,
        })),
      }));
      setMessages(loadedMessages);
    } catch (error) {
      console.error("Failed to load messages:", error);
      // 대화를 찾을 수 없으면 URL에서 제거
      router.replace("/ask");
    } finally {
      setIsLoadingMessages(false);
    }
  }, [router]);

  // 페이지 로드 시 URL의 conversation ID로 대화 로드
  useEffect(() => {
    const conversationId = searchParams.get("c");
    if (conversationId && conversationId !== currentConversationId) {
      loadConversation(conversationId);
    }
  }, [searchParams, currentConversationId, loadConversation]);

  const handleNewChat = () => {
    setMessages([]);
    setCurrentConversationId(undefined);
    router.replace("/ask");
  };

  const handleSelectConversation = async (id: string) => {
    if (id === currentConversationId) return;
    router.replace(`/ask?c=${id}`);
    await loadConversation(id);
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
    setAgentProgress(null); // Reset agent progress
    setGateClassification(null); // Reset gate classification

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
            // SSE event type - data에서 처리
            continue;
          }

          if (line.startsWith("data: ")) {
            const dataStr = line.slice(6);
            try {
              const data = JSON.parse(dataStr);

              // gate 이벤트 (도메인 분류 결과)
              if (data.category !== undefined && data.is_oncology !== undefined) {
                setGateClassification({
                  category: data.category,
                  confidence: data.confidence,
                  is_oncology: data.is_oncology,
                  warning: data.warning,
                });
              }

              // status 이벤트 (진행 상태)
              if (data.step && data.message) {
                setStatusMessage(data.message);
              }

              // complexity 이벤트 (복잡도 분석 결과)
              if (data.level && data.reasoning !== undefined) {
                setAgentProgress((prev) => ({
                  ...prev,
                  complexity: { level: data.level, reasoning: data.reasoning },
                }));
              }

              // subtasks 이벤트 (분해된 태스크 목록)
              if (data.tasks) {
                const tasks = data.tasks.map((t: SubTask) => ({
                  ...t,
                  status: "pending" as const,
                }));
                setAgentProgress((prev) => ({
                  ...prev,
                  subtasks: tasks,
                }));
              }

              // task_complete 이벤트 (태스크 완료)
              if (data.task_id && data.summary !== undefined) {
                setAgentProgress((prev) => {
                  if (!prev?.subtasks) return prev;
                  return {
                    ...prev,
                    subtasks: prev.subtasks.map((t) =>
                      t.id === data.task_id ? { ...t, status: "completed" as const } : t
                    ),
                  };
                });
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
                // URL 업데이트 (새 대화 생성 시)
                router.replace(`/ask?c=${data.conversation_id}`);
                // 새 대화가 생성되었으면 사이드바 새로고침
                setSidebarRefresh((prev) => prev + 1);
                // 완료 시 agent progress 초기화
                setAgentProgress(null);
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
        refreshTrigger={sidebarRefresh}
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
            {isLoadingMessages ? (
              // Loading State
              <div className="flex flex-col items-center justify-center min-h-[400px]">
                <Loader2 size={32} className="animate-spin text-[var(--oaria-teal)] mb-4" />
                <p className="text-[var(--oaria-text-secondary)]">대화 내용을 불러오는 중...</p>
              </div>
            ) : messages.length === 0 ? (
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
                      className={`${message.role === "user"
                        ? "max-w-[70%] bg-[var(--oaria-teal)] text-white rounded-2xl rounded-br-md px-4 py-3"
                        : "flex-1"
                        }`}
                    >
                      {message.role === "assistant" && (
                        <div className="font-[family-name:var(--font-dm-sans)] text-base mb-1 text-[var(--oaria-text-secondary)]">
                          AI Assistant
                        </div>
                      )}
                      {message.role === "user" ? (
                        <div className="font-[family-name:var(--font-dm-sans)] text-base whitespace-pre-wrap leading-relaxed">
                          {message.content}
                        </div>
                      ) : (
                        (() => {
                          const { mainContent, suggestions } = parseSuggestions(message.content);
                          return (
                            <>
                              {/* Off-domain 경고 메시지 */}
                              {gateClassification && !gateClassification.is_oncology && message.id === messages[messages.length - 1]?.id && (
                                <div className="mb-4 p-4 rounded-lg bg-amber-50 border border-amber-200">
                                  <div className="flex items-start gap-3">
                                    <AlertTriangle size={20} className="text-amber-600 flex-shrink-0 mt-0.5" />
                                    <div>
                                      <div className="font-[family-name:var(--font-outfit)] font-semibold text-amber-800 text-sm">
                                        Off-domain Query Detected
                                      </div>
                                      <p className="font-[family-name:var(--font-dm-sans)] text-sm text-amber-700 mt-1">
                                        {gateClassification.warning || `이 질문은 ${gateClassification.category} 분야로 분류되었습니다. OARIA는 종양학(암 연구) 전문 AI로, 답변의 정확도가 낮을 수 있습니다.`}
                                      </p>
                                      <div className="mt-2 text-xs text-amber-600">
                                        신뢰도: {(gateClassification.confidence * 100).toFixed(0)}%
                                      </div>
                                    </div>
                                  </div>
                                </div>
                              )}
                              <div className="font-[family-name:var(--font-dm-sans)] text-base leading-relaxed text-[var(--foreground)] prose prose-sm max-w-none prose-headings:font-semibold prose-headings:text-[var(--foreground)] prose-p:text-[var(--foreground)] prose-strong:text-[var(--foreground)] prose-li:text-[var(--foreground)]">
                                <ReactMarkdown>{mainContent}</ReactMarkdown>
                                {/* 스트리밍 중 커서 표시 */}
                                {isLoading && message.id === messages[messages.length - 1]?.id && message.content && (
                                  <span className="inline-block w-2 h-5 bg-[var(--oaria-teal)] ml-1 animate-pulse" />
                                )}
                              </div>
                              {/* 추천 질문 버튼 */}
                              {suggestions.length > 0 && !isLoading && (
                                <div className="mt-6 pt-4 border-t border-[var(--oaria-border)]">
                                  <div className="flex items-center gap-2 mb-3">
                                    <Lightbulb size={16} className="text-[var(--oaria-teal)]" />
                                    <span className="font-[family-name:var(--font-outfit)] text-sm font-medium">
                                      관련 질문
                                    </span>
                                  </div>
                                  <div className="flex flex-wrap gap-2">
                                    {suggestions.map((suggestion, idx) => (
                                      <button
                                        key={idx}
                                        onClick={() => setInput(suggestion)}
                                        className="px-3 py-2 rounded-lg border border-[var(--oaria-border)] text-sm text-[var(--oaria-text-secondary)] hover:border-[var(--oaria-teal)] hover:text-[var(--oaria-teal)] hover:bg-[var(--oaria-teal)]/5 transition-colors text-left"
                                      >
                                        {suggestion}
                                      </button>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </>
                          );
                        })()
                      )}

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

                {/* Agent Progress UI */}
                {isLoading && agentProgress && (
                  <div className="ml-11 mb-4 p-4 rounded-lg bg-[var(--oaria-border)]/20 border border-[var(--oaria-border)]">
                    {/* Complexity Badge */}
                    {agentProgress.complexity && (
                      <div className="flex items-center gap-2 mb-3">
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                          agentProgress.complexity.level === "simple"
                            ? "bg-green-100 text-green-700"
                            : agentProgress.complexity.level === "medium"
                            ? "bg-yellow-100 text-yellow-700"
                            : "bg-red-100 text-red-700"
                        }`}>
                          {agentProgress.complexity.level.toUpperCase()} Query
                        </span>
                        <span className="text-xs text-[var(--oaria-text-secondary)]">
                          {agentProgress.complexity.reasoning}
                        </span>
                      </div>
                    )}

                    {/* Subtasks List */}
                    {agentProgress.subtasks && agentProgress.subtasks.length > 0 && (
                      <div className="space-y-2">
                        <div className="text-xs font-medium text-[var(--oaria-text-secondary)] mb-2">
                          Sub-tasks ({agentProgress.subtasks.filter(t => t.status === "completed").length}/{agentProgress.subtasks.length})
                        </div>
                        {agentProgress.subtasks.map((task) => (
                          <div key={task.id} className="flex items-center gap-2 text-sm">
                            {task.status === "completed" ? (
                              <span className="w-4 h-4 rounded-full bg-green-500 flex items-center justify-center">
                                <span className="text-white text-xs">✓</span>
                              </span>
                            ) : task.status === "running" ? (
                              <Loader2 size={16} className="animate-spin text-[var(--oaria-teal)]" />
                            ) : (
                              <span className="w-4 h-4 rounded-full border border-[var(--oaria-border)]" />
                            )}
                            <span className={`${task.status === "completed" ? "text-[var(--oaria-text-secondary)]" : "text-[var(--foreground)]"}`}>
                              {task.query.length > 60 ? task.query.slice(0, 60) + "..." : task.query}
                            </span>
                            <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--oaria-border)] text-[var(--oaria-text-secondary)]">
                              {task.tool}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

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

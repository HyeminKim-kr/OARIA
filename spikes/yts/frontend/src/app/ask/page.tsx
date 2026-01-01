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

interface Reference {
  id: string;
  title: string;
  journal: string;
  year: number;
  section: string;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  references?: Reference[];
}

// 임시 응답 데이터 (실제로는 SSE로 스트리밍)
const mockReferences: Reference[] = [
  {
    id: "PMC12345",
    title: "Immunotherapy Response Prediction in Non-Small Cell Lung Cancer",
    journal: "Nature Medicine",
    year: 2025,
    section: "Results",
  },
  {
    id: "PMC23456",
    title: "CAR-T Cell Therapy Optimization for Solid Tumors",
    journal: "Cancer Cell",
    year: 2025,
    section: "Discussion",
  },
  {
    id: "PMC34567",
    title: "Combination Therapy Approaches in Lung Cancer Treatment",
    journal: "JAMA Oncology",
    year: 2024,
    section: "Methods",
  },
];

export default function AskPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [currentConversationId, setCurrentConversationId] = useState<string | undefined>();
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

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    // 임시: Mock 응답 (실제로는 SSE 스트리밍)
    setTimeout(() => {
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `최근 폐암 면역치료 연구는 크게 3가지 방향으로 진행되고 있습니다.

**1. PD-L1 발현 기반 반응 예측**
면역관문억제제(ICI)의 반응을 예측하기 위해 PD-L1 발현 수준과 함께 종양 미세환경(TME) 분석이 활발히 연구되고 있습니다. 특히 딥러닝 기반의 CT 영상 분석이 기존 바이오마커보다 높은 예측 정확도를 보이고 있습니다 [1].

**2. CAR-T 세포치료의 고형암 적용**
혈액암에서 성공적인 결과를 보인 CAR-T 세포치료를 폐암 등 고형암에 적용하기 위한 연구가 진행 중입니다. 주요 과제로는 종양 미세환경의 면역억제, 항원 이질성, T세포 소진 등이 있습니다 [2].

**3. 병용요법 연구**
화학요법과 면역치료의 조합, 또는 서로 다른 면역관문억제제의 병용이 단독 치료보다 우수한 효과를 보이는 것으로 나타나고 있습니다 [3].`,
        references: mockReferences,
      };

      setMessages((prev) => [...prev, assistantMessage]);
      setIsLoading(false);
    }, 1500);
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
                        <div className="space-y-2">
                          {message.references.map((ref, idx) => (
                            <div
                              key={ref.id}
                              className="flex items-start gap-3 p-3 rounded-lg bg-[var(--oaria-border)]/20 hover:bg-[var(--oaria-border)]/40 transition-colors group cursor-pointer"
                            >
                              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-[var(--oaria-teal)]/20 text-[var(--oaria-teal)] text-xs font-medium flex items-center justify-center">
                                {idx + 1}
                              </span>
                              <div className="flex-1 min-w-0">
                                <div className="font-[family-name:var(--font-dm-sans)] text-sm font-medium text-[var(--foreground)] group-hover:text-[var(--oaria-teal)] transition-colors line-clamp-1">
                                  {ref.title}
                                </div>
                                <div className="font-[family-name:var(--font-dm-sans)] text-xs text-[var(--oaria-tagline)] mt-0.5">
                                  {ref.journal} ({ref.year}) · {ref.section}
                                </div>
                              </div>
                              <ExternalLink
                                size={14}
                                className="text-[var(--oaria-text-secondary)] opacity-0 group-hover:opacity-100 transition-opacity"
                              />
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {/* Loading Indicator */}
              {isLoading && (
                <div className="flex gap-4">
                  <div className="w-8 h-8 rounded-full bg-[var(--oaria-teal)] flex-shrink-0 flex items-center justify-center">
                    <Bot size={18} className="text-white" />
                  </div>
                  <div className="flex items-center gap-2 text-[var(--oaria-text-secondary)]">
                    <Loader2 size={18} className="animate-spin" />
                    <span className="font-[family-name:var(--font-dm-sans)] text-base">
                      Searching papers and generating answer...
                    </span>
                  </div>
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
    </div>
  );
}

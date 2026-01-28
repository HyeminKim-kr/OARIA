"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Search,
  Bot,
  MessageSquare,
  BarChart3,
  ArrowLeft,
  BookOpen,
  Send,
  FileText,
  TrendingUp,
  Library,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Loader2,
} from "lucide-react";

// ─────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  sources?: Source[];
}

interface Source {
  title: string;
  authors?: string;
  journal?: string;
  year?: number;
  url?: string;
}

interface ExampleQuestion {
  category: string;
  icon: React.ReactNode;
  questions: string[];
}

// ─────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────

const EXAMPLE_QUESTIONS: ExampleQuestion[] = [
  {
    category: "논문 분석",
    icon: <FileText size={18} />,
    questions: [
      "EGFR 변이 비소세포폐암의 최신 표적치료제 연구 동향을 분석해주세요.",
      "면역관문억제제의 병용요법 효과에 대한 최근 임상연구를 요약해주세요.",
      "CAR-T 세포치료의 고형암 적용 가능성에 대한 연구를 분석해주세요.",
    ],
  },
  {
    category: "연구 동향",
    icon: <TrendingUp size={18} />,
    questions: [
      "2024년 암 면역요법 분야의 주요 연구 트렌드는 무엇인가요?",
      "정밀의료 기반 암 진단의 최신 기술 발전을 알려주세요.",
      "액체생검 기술의 임상 적용 현황과 전망은 어떤가요?",
    ],
  },
  {
    category: "문헌 고찰",
    icon: <Library size={18} />,
    questions: [
      "PD-1/PD-L1 억제제의 바이오마커 연구에 대해 체계적 문헌 고찰을 해주세요.",
      "KRAS G12C 변이 표적치료제의 임상 데이터를 종합해주세요.",
      "암 줄기세포 관련 치료 전략의 연구 현황을 정리해주세요.",
    ],
  },
];

const FAQ_ITEMS = [
  {
    question: "Research Assistant는 어떤 기능을 제공하나요?",
    answer:
      "Research Assistant는 암 연구 논문 분석, 최신 연구 동향 파악, 체계적 문헌 고찰을 지원합니다. RAG 기반으로 실제 논문 데이터를 검색하여 정확한 정보를 제공합니다.",
  },
  {
    question: "어떤 종류의 질문을 할 수 있나요?",
    answer:
      "특정 암종의 치료법, 바이오마커, 임상시험 결과, 약물 작용 기전, 연구 방법론 등 암 연구와 관련된 다양한 질문을 하실 수 있습니다. 가능한 구체적으로 질문해주시면 더 정확한 답변을 받으실 수 있습니다.",
  },
  {
    question: "답변의 출처는 어디인가요?",
    answer:
      "답변은 OARIA 데이터베이스에 수집된 암 연구 논문들을 기반으로 생성됩니다. 각 답변에는 참조된 논문의 정보가 함께 제공되어 출처를 확인하실 수 있습니다.",
  },
  {
    question: "Study Plan Agent와 어떻게 다른가요?",
    answer:
      "Study Plan Agent는 가설을 기반으로 후속 실험을 설계하는 데 특화되어 있습니다. Research Assistant는 기존 연구에 대한 분석, 요약, 동향 파악에 초점을 맞추어 연구 이해를 돕는 역할을 합니다.",
  },
];

// ─────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────

export default function ResearchAssistantPage() {
  const [viewMode, setViewMode] = useState<"landing" | "chat">("landing");
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [openFaqIndex, setOpenFaqIndex] = useState<number | null>(null);

  const handleExampleClick = (question: string) => {
    setQuery(question);
    setViewMode("chat");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isLoading) return;

    const userMessage: Message = {
      id: `msg-${Date.now()}`,
      role: "user",
      content: query.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setQuery("");
    setIsLoading(true);

    // TODO: 실제 API 연동 - 현재는 플레이스홀더
    setTimeout(() => {
      const assistantMessage: Message = {
        id: `msg-${Date.now()}-assistant`,
        role: "assistant",
        content:
          "Research Assistant 기능은 현재 개발 중입니다. 곧 RAG 기반의 논문 분석, 연구 동향 파악, 문헌 고찰 기능을 사용하실 수 있습니다.",
        timestamp: new Date(),
        sources: [
          {
            title: "Sample Paper Title",
            authors: "Kim et al.",
            journal: "Nature Cancer",
            year: 2024,
          },
        ],
      };
      setMessages((prev) => [...prev, assistantMessage]);
      setIsLoading(false);
    }, 1500);
  };

  const toggleFaq = (index: number) => {
    setOpenFaqIndex(openFaqIndex === index ? null : index);
  };

  // ─────────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────────

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header with Tabs */}
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
              className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-[var(--oaria-teal)] text-[var(--oaria-teal)]"
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

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto">
        {viewMode === "landing" ? (
          // ─────────────────────────────────────────────────────────────
          // Landing View
          // ─────────────────────────────────────────────────────────────
          <div className="max-w-5xl mx-auto px-6 py-8">
            {/* Hero Section */}
            <div className="text-center mb-12">
              <div className="w-20 h-20 rounded-2xl bg-[#1E293B] flex items-center justify-center mx-auto mb-6 shadow-lg">
                <BookOpen size={40} className="text-white" />
              </div>
              <h1 className="font-[family-name:var(--font-outfit)] text-3xl font-semibold mb-3">
                Research Assistant
              </h1>
              <p className="font-[family-name:var(--font-dm-sans)] text-lg text-[var(--oaria-text-secondary)] max-w-2xl mx-auto mb-6">
                암 연구 논문 분석, 연구 동향 파악, 체계적 문헌 고찰을 도와드립니다.
                <br />
                RAG 기반으로 실제 논문 데이터를 검색하여 정확한 정보를 제공합니다.
              </p>
              <button
                onClick={() => setViewMode("chat")}
                className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-[#1E293B] text-white font-medium hover:bg-[#334155] transition-colors"
              >
                <Sparkles size={20} />
                시작하기
              </button>
            </div>

            {/* Feature Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-12">
              <div className="p-6 rounded-xl border border-[var(--oaria-border)] bg-[var(--background)]">
                <div className="w-12 h-12 rounded-xl bg-blue-100 flex items-center justify-center mb-4">
                  <FileText size={24} className="text-blue-600" />
                </div>
                <h3 className="font-[family-name:var(--font-outfit)] text-lg font-semibold mb-2">
                  논문 분석
                </h3>
                <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)]">
                  특정 주제나 논문에 대한 심층 분석을 제공합니다. 연구 방법론, 결과,
                  한계점 등을 종합적으로 파악할 수 있습니다.
                </p>
              </div>
              <div className="p-6 rounded-xl border border-[var(--oaria-border)] bg-[var(--background)]">
                <div className="w-12 h-12 rounded-xl bg-green-100 flex items-center justify-center mb-4">
                  <TrendingUp size={24} className="text-green-600" />
                </div>
                <h3 className="font-[family-name:var(--font-outfit)] text-lg font-semibold mb-2">
                  동향 파악
                </h3>
                <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)]">
                  최신 연구 트렌드와 발전 방향을 파악합니다. 분야별 주요 연구 흐름과
                  새로운 기술 동향을 확인할 수 있습니다.
                </p>
              </div>
              <div className="p-6 rounded-xl border border-[var(--oaria-border)] bg-[var(--background)]">
                <div className="w-12 h-12 rounded-xl bg-purple-100 flex items-center justify-center mb-4">
                  <Library size={24} className="text-purple-600" />
                </div>
                <h3 className="font-[family-name:var(--font-outfit)] text-lg font-semibold mb-2">
                  문헌 고찰
                </h3>
                <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)]">
                  체계적 문헌 고찰을 지원합니다. 관련 연구들을 종합하여 현재까지의
                  연구 현황을 정리해 드립니다.
                </p>
              </div>
            </div>

            {/* Example Questions */}
            <div className="mb-12">
              <h2 className="font-[family-name:var(--font-outfit)] text-xl font-semibold mb-6 text-center">
                이런 질문을 해보세요
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {EXAMPLE_QUESTIONS.map((category) => (
                  <div key={category.category}>
                    <div className="flex items-center gap-2 mb-3">
                      <span className="text-[var(--oaria-text-secondary)]">
                        {category.icon}
                      </span>
                      <span className="font-[family-name:var(--font-dm-sans)] text-sm font-medium text-[var(--oaria-text-secondary)]">
                        {category.category}
                      </span>
                    </div>
                    <div className="space-y-2">
                      {category.questions.map((question, idx) => (
                        <button
                          key={idx}
                          onClick={() => handleExampleClick(question)}
                          className="w-full text-left p-3 rounded-lg border border-[var(--oaria-border)] hover:border-[#1E293B] hover:bg-[#1E293B]/5 transition-colors"
                        >
                          <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--foreground)]">
                            {question}
                          </p>
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* FAQ Section */}
            <div className="max-w-3xl mx-auto">
              <h2 className="font-[family-name:var(--font-outfit)] text-xl font-semibold mb-6 text-center">
                자주 묻는 질문
              </h2>
              <div className="space-y-3">
                {FAQ_ITEMS.map((faq, index) => (
                  <div
                    key={index}
                    className="border border-[var(--oaria-border)] rounded-xl overflow-hidden"
                  >
                    <button
                      onClick={() => toggleFaq(index)}
                      className="w-full flex items-center justify-between p-4 text-left hover:bg-[var(--oaria-border-light)] transition-colors"
                    >
                      <span className="font-[family-name:var(--font-dm-sans)] font-medium">
                        {faq.question}
                      </span>
                      {openFaqIndex === index ? (
                        <ChevronUp size={20} className="text-[var(--oaria-text-secondary)]" />
                      ) : (
                        <ChevronDown size={20} className="text-[var(--oaria-text-secondary)]" />
                      )}
                    </button>
                    {openFaqIndex === index && (
                      <div className="px-4 pb-4">
                        <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)]">
                          {faq.answer}
                        </p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          // ─────────────────────────────────────────────────────────────
          // Chat View
          // ─────────────────────────────────────────────────────────────
          <div className="flex flex-col h-full">
            {/* Chat Header */}
            <div className="max-w-4xl w-full mx-auto px-6 py-4">
              <div className="flex items-center gap-4">
                <button
                  onClick={() => {
                    setViewMode("landing");
                    setMessages([]);
                    setQuery("");
                  }}
                  className="p-2 rounded-lg hover:bg-[var(--oaria-border)] transition-colors"
                >
                  <ArrowLeft size={20} />
                </button>
                <div className="w-10 h-10 rounded-xl bg-[#1E293B] flex items-center justify-center text-white">
                  <BookOpen size={20} />
                </div>
                <div>
                  <h1 className="font-[family-name:var(--font-outfit)] text-lg font-semibold">
                    Research Assistant
                  </h1>
                  <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)]">
                    연구 분석 에이전트
                  </p>
                </div>
              </div>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto px-6">
              <div className="max-w-4xl mx-auto space-y-6 py-4">
                {messages.length === 0 ? (
                  // Empty State
                  <div className="text-center py-12">
                    <div className="w-16 h-16 rounded-2xl bg-[#1E293B]/10 flex items-center justify-center mx-auto mb-4">
                      <BookOpen size={32} className="text-[#1E293B]" />
                    </div>
                    <h2 className="font-[family-name:var(--font-outfit)] text-xl font-semibold mb-2">
                      무엇을 도와드릴까요?
                    </h2>
                    <p className="font-[family-name:var(--font-dm-sans)] text-[var(--oaria-text-secondary)] mb-8">
                      암 연구에 대해 궁금한 점을 질문해주세요.
                    </p>

                    {/* Quick Examples */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-2xl mx-auto">
                      {EXAMPLE_QUESTIONS.flatMap((cat) => cat.questions.slice(0, 1)).map(
                        (question, idx) => (
                          <button
                            key={idx}
                            onClick={() => handleExampleClick(question)}
                            className="p-4 rounded-xl border border-[var(--oaria-border)] hover:border-[#1E293B] hover:bg-[#1E293B]/5 text-left transition-colors"
                          >
                            <p className="font-[family-name:var(--font-dm-sans)] text-sm">
                              {question}
                            </p>
                          </button>
                        )
                      )}
                    </div>
                  </div>
                ) : (
                  // Message List
                  messages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
                    >
                      <div
                        className={`max-w-[80%] ${
                          message.role === "user"
                            ? "bg-[#1E293B] text-white rounded-2xl rounded-br-md"
                            : "bg-[var(--oaria-border-light)] rounded-2xl rounded-bl-md"
                        } p-4`}
                      >
                        <p className="font-[family-name:var(--font-dm-sans)] text-sm whitespace-pre-wrap">
                          {message.content}
                        </p>

                        {/* Sources */}
                        {message.sources && message.sources.length > 0 && (
                          <div className="mt-4 pt-3 border-t border-[var(--oaria-border)]">
                            <p className="font-[family-name:var(--font-dm-sans)] text-xs font-medium text-[var(--oaria-text-secondary)] mb-2">
                              참고 문헌
                            </p>
                            <div className="space-y-2">
                              {message.sources.map((source, idx) => (
                                <div
                                  key={idx}
                                  className="text-xs text-[var(--oaria-text-secondary)]"
                                >
                                  <span className="font-medium">{source.title}</span>
                                  {source.authors && ` - ${source.authors}`}
                                  {source.journal && `, ${source.journal}`}
                                  {source.year && ` (${source.year})`}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  ))
                )}

                {/* Loading Indicator */}
                {isLoading && (
                  <div className="flex justify-start">
                    <div className="bg-[var(--oaria-border-light)] rounded-2xl rounded-bl-md p-4">
                      <div className="flex items-center gap-2 text-[var(--oaria-text-secondary)]">
                        <Loader2 size={16} className="animate-spin" />
                        <span className="font-[family-name:var(--font-dm-sans)] text-sm">
                          답변을 생성하고 있습니다...
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Input Area */}
            <div className="border-t border-[var(--oaria-border)] bg-[var(--background)]">
              <div className="max-w-4xl mx-auto px-6 py-4">
                <form onSubmit={handleSubmit} className="flex gap-3">
                  <input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="암 연구에 대해 질문해주세요..."
                    className="flex-1 px-4 py-3 rounded-xl border border-[var(--oaria-border)] bg-[var(--background)] focus:outline-none focus:ring-2 focus:ring-[#1E293B]/20 focus:border-[#1E293B] font-[family-name:var(--font-dm-sans)]"
                    disabled={isLoading}
                  />
                  <button
                    type="submit"
                    disabled={!query.trim() || isLoading}
                    className="px-6 py-3 rounded-xl bg-[#1E293B] text-white font-medium hover:bg-[#334155] disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                  >
                    <Send size={18} />
                    <span>전송</span>
                  </button>
                </form>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

"use client";

import Link from "next/link";
import {
  Search,
  Bot,
  MessageSquare,
  FileText,
  Beaker,
  BookOpen,
  TrendingUp,
  ArrowRight,
  BarChart3,
  Mic2,
} from "lucide-react";

interface AgentCard {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  href: string;
  color: string;
  comingSoon?: boolean;
}

const agents: AgentCard[] = [
  {
    id: "study-plan",
    name: "Study Plan Agent",
    description: "가설 기반 후속 실험 설계를 자동화합니다. NSPE 분석, Evidence Pack 구축, 실험 설계를 지원합니다.",
    icon: <Beaker size={24} />,
    href: "/agents/study-plan",
    color: "bg-green-500",
  },
  {
    id: "podcast",
    name: "Podcast Agent",
    description: "암 연구 논문을 기반으로 팟캐스트 스크립트를 생성합니다. RAG 기반 인용과 다양한 대화 스타일을 지원합니다.",
    icon: <Mic2 size={24} />,
    href: "/agents/podcast",
    color: "bg-purple-500",
  },
  {
    id: "research-assistant",
    name: "Research Assistant",
    description: "논문 분석, 연구 동향 파악, 관련 연구 탐색을 도와드립니다.",
    icon: <BookOpen size={24} />,
    href: "/agents/research-assistant",
    color: "bg-blue-500",
    comingSoon: true,
  },
  {
    id: "literature-review",
    name: "Literature Review",
    description: "체계적 문헌 고찰을 위한 논문 수집, 분류, 요약을 지원합니다.",
    icon: <FileText size={24} />,
    href: "/agents/literature-review",
    color: "bg-purple-500",
    comingSoon: true,
  },
  {
    id: "trend-analyzer",
    name: "Trend Analyzer",
    description: "연구 분야의 트렌드 분석, 핫토픽 발굴을 지원합니다.",
    icon: <TrendingUp size={24} />,
    href: "/agents/trend-analyzer",
    color: "bg-orange-500",
    comingSoon: true,
  },
];

export default function AgentsPage() {
  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header with Tabs - Fixed */}
      <div className="bg-[var(--background)]">
        <div className="flex items-center justify-center">
          {/* Navigation Tabs */}
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
            <button
              type="button"
              className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-[var(--oaria-teal)] text-[var(--oaria-teal)]"
            >
              <Bot size={20} />
              Agents
            </button>
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
        <div className="max-w-5xl mx-auto px-6 py-8">
          {/* Page Header */}
          <div className="text-center mb-10">
            <div className="w-16 h-16 rounded-full bg-[var(--oaria-teal)]/10 flex items-center justify-center mx-auto mb-4">
              <Bot size={32} className="text-[var(--oaria-teal)]" />
            </div>
            <h1 className="font-[family-name:var(--font-outfit)] text-3xl font-semibold mb-2">
              AI Agents
            </h1>
            <p className="font-[family-name:var(--font-dm-sans)] text-base text-[var(--oaria-text-secondary)] max-w-md mx-auto">
              전문화된 AI 에이전트를 선택하여 연구 작업을 효율적으로 수행하세요.
            </p>
          </div>

          {/* Agent Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {agents.map((agent) => (
              <Link
                key={agent.id}
                href={agent.comingSoon ? "#" : agent.href}
                className={`group relative p-6 rounded-xl border-2 border-[var(--oaria-border-strong)] bg-[var(--background)] hover:border-[var(--oaria-teal)]/50 hover:shadow-lg transition-all ${
                  agent.comingSoon ? "opacity-60 cursor-not-allowed" : ""
                }`}
                onClick={(e) => agent.comingSoon && e.preventDefault()}
              >
                {/* Coming Soon Badge */}
                {agent.comingSoon && (
                  <span className="absolute top-4 right-4 px-2 py-1 rounded-full bg-[var(--oaria-border)] text-xs font-medium text-[var(--oaria-text-secondary)]">
                    Coming Soon
                  </span>
                )}

                {/* Icon */}
                <div
                  className={`w-12 h-12 rounded-xl ${agent.color} flex items-center justify-center mb-4 text-white`}
                >
                  {agent.icon}
                </div>

                {/* Content */}
                <h3 className="font-[family-name:var(--font-outfit)] text-lg font-semibold mb-2 group-hover:text-[var(--oaria-teal)] transition-colors">
                  {agent.name}
                </h3>
                <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] mb-4">
                  {agent.description}
                </p>

                {/* Action */}
                {!agent.comingSoon && (
                  <div className="flex items-center gap-2 text-sm font-medium text-[var(--oaria-teal)] opacity-0 group-hover:opacity-100 transition-opacity">
                    시작하기
                    <ArrowRight size={16} />
                  </div>
                )}
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

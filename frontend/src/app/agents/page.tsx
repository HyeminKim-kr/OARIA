"use client";

import Link from "next/link";
import {
  Search,
  Bot,
  MessageSquare,
  Beaker,
  ArrowRight,
  BarChart3,
  Mic2,
  BookOpen,
} from "lucide-react";

interface AgentCard {
  id: string;
  name: string;
  subtitle: string;
  description: string;
  features: string[];
  icon: React.ReactNode;
  href: string;
  accentColor: string; // CSS variable or hex
  bgGradientFrom: string;
  bgGradientTo: string;
  iconBg: string;
  comingSoon?: boolean;
}

const agents: AgentCard[] = [
  {
    id: "study-plan",
    name: "Study Plan",
    subtitle: "실험 설계 에이전트",
    description:
      "가설 기반 후속 실험 설계를 자동화합니다. NSPE 분석, Evidence Pack 구축, 실험 설계를 지원합니다.",
    features: ["NSPE 분석", "Evidence Pack", "실험 프로토콜 생성"],
    icon: <Beaker size={28} />,
    href: "/agents/study-plan",
    accentColor: "#F97066",
    bgGradientFrom: "from-[#F97066]/10",
    bgGradientTo: "to-[#F97066]/5",
    iconBg: "bg-[#F97066]",
  },
  {
    id: "podcast",
    name: "Podcast",
    subtitle: "팟캐스트 생성 에이전트",
    description:
      "암 연구 논문을 기반으로 팟캐스트를 생성합니다. RAG 기반 인용과 다양한 대화 스타일, TTS 음성을 지원합니다.",
    features: ["다중 화자 TTS", "RAG 기반 인용", "실시간 대사 추적"],
    icon: <Mic2 size={28} />,
    href: "/agents/podcast",
    accentColor: "#94A3B8",
    bgGradientFrom: "from-[#94A3B8]/10",
    bgGradientTo: "to-[#94A3B8]/5",
    iconBg: "bg-[#94A3B8]",
  },
  {
    id: "research-assistant",
    name: "Research Assistant",
    subtitle: "연구 분석 에이전트",
    description:
      "논문 분석, 연구 동향 파악, 관련 연구 탐색을 도와드립니다. 체계적 문헌 고찰을 지원합니다.",
    features: ["논문 분석", "동향 파악", "문헌 고찰"],
    icon: <BookOpen size={28} />,
    href: "/agents/research-assistant",
    accentColor: "#1E293B",
    bgGradientFrom: "from-[#1E293B]/10",
    bgGradientTo: "to-[#1E293B]/5",
    iconBg: "bg-[#1E293B]",
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
        <div className="max-w-6xl mx-auto px-6 py-8">
          {/* Page Header */}
          <div className="text-center mb-12">
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

          {/* Agent Cards - 3 tall vertical boxes in a row */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {agents.map((agent) => (
              <Link
                key={agent.id}
                href={agent.comingSoon ? "#" : agent.href}
                className={`group relative flex flex-col rounded-2xl border-2 border-[var(--oaria-border-strong)] bg-[var(--background)] overflow-hidden transition-all duration-300 hover:shadow-xl ${
                  agent.comingSoon
                    ? "opacity-60 cursor-not-allowed"
                    : "hover:-translate-y-1"
                }`}
                style={{
                  ["--card-accent" as string]: agent.accentColor,
                }}
                onClick={(e) => agent.comingSoon && e.preventDefault()}
              >
                {/* Top accent gradient */}
                <div
                  className={`h-32 bg-gradient-to-b ${agent.bgGradientFrom} ${agent.bgGradientTo} flex items-center justify-center relative`}
                >
                  {/* Coming Soon Badge */}
                  {agent.comingSoon && (
                    <span className="absolute top-4 right-4 px-3 py-1 rounded-full bg-[var(--oaria-border)] text-xs font-medium text-[var(--oaria-text-secondary)]">
                      Coming Soon
                    </span>
                  )}

                  {/* Icon */}
                  <div
                    className={`w-16 h-16 rounded-2xl ${agent.iconBg} flex items-center justify-center text-white shadow-lg`}
                  >
                    {agent.icon}
                  </div>
                </div>

                {/* Content */}
                <div className="flex flex-col flex-1 p-6">
                  <h3 className="font-[family-name:var(--font-outfit)] text-xl font-semibold mb-1">
                    {agent.name}
                  </h3>
                  <p
                    className="font-[family-name:var(--font-dm-sans)] text-xs font-medium mb-4"
                    style={{ color: agent.accentColor }}
                  >
                    {agent.subtitle}
                  </p>
                  <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] mb-6 leading-relaxed">
                    {agent.description}
                  </p>

                  {/* Feature tags */}
                  <div className="flex flex-wrap gap-2 mb-6">
                    {agent.features.map((feature) => (
                      <span
                        key={feature}
                        className="px-3 py-1 rounded-full text-xs font-medium border border-[var(--oaria-border)]"
                        style={{
                          color: agent.accentColor,
                          backgroundColor: `${agent.accentColor}10`,
                        }}
                      >
                        {feature}
                      </span>
                    ))}
                  </div>

                  {/* Spacer to push action to bottom */}
                  <div className="flex-1" />

                  {/* Action */}
                  {!agent.comingSoon && (
                    <div
                      className="flex items-center gap-2 text-sm font-semibold opacity-0 group-hover:opacity-100 transition-opacity"
                      style={{ color: agent.accentColor }}
                    >
                      시작하기
                      <ArrowRight
                        size={16}
                        className="group-hover:translate-x-1 transition-transform"
                      />
                    </div>
                  )}
                </div>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

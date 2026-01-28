"use client";

import Link from "next/link";
import {
  Search,
  Bot,
  MessageSquare,
  BarChart3,
  TrendingUp,
  FileText,
  Users,
  Calendar,
} from "lucide-react";

export default function DashboardPage() {
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
            <Link
              href="/agents"
              className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-colors"
            >
              <Bot size={20} />
              Agents
            </Link>
            <button
              type="button"
              className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-[var(--oaria-teal)] text-[var(--oaria-teal)]"
            >
              <BarChart3 size={20} />
              Dashboard
            </button>
          </div>
        </div>
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-6xl mx-auto px-6 py-8">
          {/* Page Header */}
          <div className="mb-8">
            <h1 className="font-[family-name:var(--font-outfit)] text-3xl font-semibold mb-2">
              Dashboard
            </h1>
            <p className="font-[family-name:var(--font-dm-sans)] text-base text-[var(--oaria-text-secondary)]">
              연구 활동 현황과 트렌드를 한눈에 확인하세요.
            </p>
          </div>

          {/* Stats Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            <div className="p-6 rounded-xl border-2 border-[var(--oaria-border-strong)] bg-[var(--background)]">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
                  <FileText size={20} className="text-blue-500" />
                </div>
                <span className="text-sm text-[var(--oaria-text-secondary)]">총 논문</span>
              </div>
              <p className="font-[family-name:var(--font-outfit)] text-3xl font-semibold">1,234</p>
              <p className="text-xs text-green-500 mt-1">+12% from last month</p>
            </div>

            <div className="p-6 rounded-xl border-2 border-[var(--oaria-border-strong)] bg-[var(--background)]">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center">
                  <MessageSquare size={20} className="text-purple-500" />
                </div>
                <span className="text-sm text-[var(--oaria-text-secondary)]">AI 질문</span>
              </div>
              <p className="font-[family-name:var(--font-outfit)] text-3xl font-semibold">256</p>
              <p className="text-xs text-green-500 mt-1">+8% from last week</p>
            </div>

            <div className="p-6 rounded-xl border-2 border-[var(--oaria-border-strong)] bg-[var(--background)]">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center">
                  <TrendingUp size={20} className="text-green-500" />
                </div>
                <span className="text-sm text-[var(--oaria-text-secondary)]">검색 횟수</span>
              </div>
              <p className="font-[family-name:var(--font-outfit)] text-3xl font-semibold">892</p>
              <p className="text-xs text-green-500 mt-1">+15% from last week</p>
            </div>

            <div className="p-6 rounded-xl border-2 border-[var(--oaria-border-strong)] bg-[var(--background)]">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 rounded-lg bg-orange-500/10 flex items-center justify-center">
                  <Users size={20} className="text-orange-500" />
                </div>
                <span className="text-sm text-[var(--oaria-text-secondary)]">북마크</span>
              </div>
              <p className="font-[family-name:var(--font-outfit)] text-3xl font-semibold">48</p>
              <p className="text-xs text-[var(--oaria-text-secondary)] mt-1">Last updated today</p>
            </div>
          </div>

          {/* Charts Section - Placeholder */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Research Trends */}
            <div className="p-6 rounded-xl border-2 border-[var(--oaria-border-strong)] bg-[var(--background)]">
              <div className="flex items-center justify-between mb-6">
                <h3 className="font-[family-name:var(--font-outfit)] text-lg font-semibold">
                  연구 트렌드
                </h3>
                <select className="px-3 py-1.5 rounded-lg border border-[var(--oaria-border)] text-sm bg-[var(--background)]">
                  <option>최근 7일</option>
                  <option>최근 30일</option>
                  <option>최근 90일</option>
                </select>
              </div>
              <div className="h-64 flex items-center justify-center text-[var(--oaria-text-secondary)]">
                <div className="text-center">
                  <BarChart3 size={48} className="mx-auto mb-3 opacity-30" />
                  <p className="text-sm">차트가 곧 추가됩니다</p>
                </div>
              </div>
            </div>

            {/* Popular Keywords */}
            <div className="p-6 rounded-xl border-2 border-[var(--oaria-border-strong)] bg-[var(--background)]">
              <div className="flex items-center justify-between mb-6">
                <h3 className="font-[family-name:var(--font-outfit)] text-lg font-semibold">
                  인기 키워드
                </h3>
                <button className="text-sm text-[var(--oaria-teal)]">전체보기</button>
              </div>
              <div className="space-y-3">
                {[
                  { keyword: "Immunotherapy", count: 156, trend: "+12%" },
                  { keyword: "CAR-T", count: 134, trend: "+8%" },
                  { keyword: "PD-1 inhibitors", count: 98, trend: "+5%" },
                  { keyword: "Lung cancer", count: 87, trend: "+3%" },
                  { keyword: "Checkpoint inhibitors", count: 76, trend: "+2%" },
                ].map((item, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between py-2 border-b border-[var(--oaria-border)] last:border-0"
                  >
                    <div className="flex items-center gap-3">
                      <span className="w-6 h-6 rounded-full bg-[var(--oaria-teal)]/10 text-[var(--oaria-teal)] text-xs font-medium flex items-center justify-center">
                        {idx + 1}
                      </span>
                      <span className="font-[family-name:var(--font-dm-sans)] text-sm">
                        {item.keyword}
                      </span>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className="text-sm text-[var(--oaria-text-secondary)]">
                        {item.count}건
                      </span>
                      <span className="text-xs text-green-500">{item.trend}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Recent Activity */}
          <div className="mt-6 p-6 rounded-xl border-2 border-[var(--oaria-border-strong)] bg-[var(--background)]">
            <div className="flex items-center justify-between mb-6">
              <h3 className="font-[family-name:var(--font-outfit)] text-lg font-semibold">
                최근 활동
              </h3>
              <button className="text-sm text-[var(--oaria-teal)]">전체보기</button>
            </div>
            <div className="space-y-4">
              {[
                {
                  action: "논문 검색",
                  detail: '"CAR-T cell therapy" 검색',
                  time: "5분 전",
                  icon: <Search size={16} />,
                },
                {
                  action: "AI 질문",
                  detail: '"What are the latest advances in immunotherapy?"',
                  time: "12분 전",
                  icon: <MessageSquare size={16} />,
                },
                {
                  action: "논문 북마크",
                  detail: '"Advances in RNA-based cancer therapeutics"',
                  time: "1시간 전",
                  icon: <FileText size={16} />,
                },
              ].map((item, idx) => (
                <div
                  key={idx}
                  className="flex items-start gap-4 py-3 border-b border-[var(--oaria-border)] last:border-0"
                >
                  <div className="w-8 h-8 rounded-lg bg-[var(--oaria-border)]/50 flex items-center justify-center text-[var(--oaria-text-secondary)]">
                    {item.icon}
                  </div>
                  <div className="flex-1">
                    <p className="font-[family-name:var(--font-dm-sans)] text-sm font-medium">
                      {item.action}
                    </p>
                    <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] mt-0.5">
                      {item.detail}
                    </p>
                  </div>
                  <span className="text-xs text-[var(--oaria-tagline)]">{item.time}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

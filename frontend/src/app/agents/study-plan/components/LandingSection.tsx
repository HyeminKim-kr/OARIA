"use client";

import Link from "next/link";
import {
  ArrowLeft,
  BookOpen,
  History,
  Sparkles,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { features, faqs } from "../constants";

interface LandingSectionProps {
  onStartGenerate: () => void;
  openFaqIndex: number | null;
  onToggleFaq: (index: number) => void;
}

export function LandingSection({
  onStartGenerate,
  openFaqIndex,
  onToggleFaq,
}: LandingSectionProps) {
  return (
    <>
      {/* Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-b from-[var(--oaria-teal)]/5 to-transparent">
        <div className="max-w-5xl mx-auto px-6 py-16">
          {/* Back to Agents - Left aligned */}
          <div className="mb-6 text-left">
            <Link
              href="/agents"
              className="inline-flex items-center gap-1 text-sm text-[var(--oaria-text-secondary)] hover:text-[var(--oaria-teal)] transition-colors"
            >
              <ArrowLeft size={16} />
              모든 에이전트
            </Link>
          </div>

          {/* Icon Badge - Center aligned */}
          <div className="mb-6 text-center">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[var(--oaria-teal)]/10 border border-[var(--oaria-teal)]/20">
              <Sparkles size={16} className="text-[var(--oaria-teal)]" />
              <span className="font-[family-name:var(--font-dm-sans)] text-sm font-medium text-[var(--oaria-teal)]">
                AI-Powered Research
              </span>
            </div>
          </div>

          {/* Main Title */}
          <h1 className="font-[family-name:var(--font-outfit)] text-4xl md:text-5xl font-bold mb-4 leading-tight text-center">
            <span className="text-[var(--foreground)]">Study Plan Agent</span>
          </h1>

          {/* Subtitle */}
          <p className="font-[family-name:var(--font-dm-sans)] text-lg text-[var(--oaria-text-secondary)] max-w-2xl mx-auto mb-8 leading-relaxed text-center">
            가설을 입력하면 AI가 체계적인 실험 설계 계획서를 자동으로 생성합니다.
            <br />
            선행 연구 검색부터 실험 설계까지, 연구 계획의 전 과정을 지원합니다.
          </p>

          {/* CTA Buttons */}
          <div className="flex items-center justify-center gap-4">
            <button
              onClick={onStartGenerate}
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-[var(--oaria-teal)] text-white font-[family-name:var(--font-dm-sans)] font-medium hover:bg-[#0B7A70] transition-colors shadow-lg shadow-[var(--oaria-teal)]/20"
            >
              <BookOpen size={20} />
              실험 계획 시작하기
            </button>
            <Link
              href="/agents/study-plan/history"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl border-2 border-[var(--oaria-border-strong)] bg-[var(--background)] text-[var(--foreground)] font-[family-name:var(--font-dm-sans)] font-medium hover:border-[var(--oaria-teal)] hover:text-[var(--oaria-teal)] transition-colors"
            >
              <History size={20} />
              내 기록 보기
            </Link>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="max-w-5xl mx-auto px-6 py-12">
        <div className="text-center mb-10">
          <h2 className="font-[family-name:var(--font-outfit)] text-2xl font-semibold mb-2">
            주요 기능
          </h2>
          <p className="font-[family-name:var(--font-dm-sans)] text-[var(--oaria-text-secondary)]">
            연구자의 실험 설계 과정을 AI가 체계적으로 지원합니다
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {features.map((feature, index) => (
            <div
              key={index}
              className="p-6 rounded-xl border-2 border-[var(--oaria-border)] bg-[var(--background)] hover:border-[var(--oaria-teal)]/30 transition-colors"
            >
              <div className="w-12 h-12 rounded-xl bg-[var(--oaria-teal)]/10 flex items-center justify-center mb-4">
                {feature.icon}
              </div>
              <h3 className="font-[family-name:var(--font-outfit)] text-lg font-semibold mb-2">
                {feature.title}
              </h3>
              <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] leading-relaxed">
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* FAQ Section */}
      <section className="max-w-3xl mx-auto px-6 py-12 pb-16">
        <div className="text-center mb-10">
          <h2 className="font-[family-name:var(--font-outfit)] text-2xl font-semibold mb-2">
            자주 묻는 질문
          </h2>
          <p className="font-[family-name:var(--font-dm-sans)] text-[var(--oaria-text-secondary)]">
            Study Plan Agent에 대해 궁금한 점을 확인하세요
          </p>
        </div>

        <div className="space-y-3">
          {faqs.map((faq, index) => (
            <div
              key={index}
              className="border-2 border-[var(--oaria-border)] rounded-xl overflow-hidden"
            >
              <button
                type="button"
                onClick={() => onToggleFaq(index)}
                className="w-full flex items-center justify-between p-4 text-left bg-[var(--background)] hover:bg-[var(--oaria-teal)]/5 transition-colors"
              >
                <span className="font-[family-name:var(--font-dm-sans)] font-medium pr-4">
                  {faq.question}
                </span>
                {openFaqIndex === index ? (
                  <ChevronUp
                    size={20}
                    className="text-[var(--oaria-teal)] flex-shrink-0"
                  />
                ) : (
                  <ChevronDown
                    size={20}
                    className="text-[var(--oaria-text-secondary)] flex-shrink-0"
                  />
                )}
              </button>
              {openFaqIndex === index && (
                <div className="px-4 pb-4 bg-[var(--background)]">
                  <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] leading-relaxed">
                    {faq.answer}
                  </p>
                </div>
              )}
            </div>
          ))}
        </div>
      </section>
    </>
  );
}

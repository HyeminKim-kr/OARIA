"use client";

import { useState } from "react";
import { EXAMPLE_QUESTIONS } from "@/lib/constants";

interface QuestionInputPanelProps {
  onSubmit: (question: string) => void;
  isProcessing: boolean;
}

export default function QuestionInputPanel({
  onSubmit,
  isProcessing,
}: QuestionInputPanelProps) {
  const [question, setQuestion] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || isProcessing) return;
    onSubmit(question.trim());
  };

  const handleExampleClick = (q: string) => {
    setQuestion(q);
  };

  return (
    <div className="absolute inset-0 flex items-center justify-center z-50">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />

      {/* Panel */}
      <div
        className="relative w-full max-w-2xl mx-4 rounded-2xl overflow-hidden shadow-2xl"
        style={{
          background: "rgba(10, 14, 26, 0.95)",
          backdropFilter: "blur(24px)",
          border: "1px solid rgba(255, 255, 255, 0.1)",
          animation: "fadeSlideUp 0.4s ease-out",
        }}
      >
        <style jsx>{`
          @keyframes fadeSlideUp {
            from {
              opacity: 0;
              transform: translateY(20px);
            }
            to {
              opacity: 1;
              transform: translateY(0);
            }
          }
        `}</style>

        {/* Header */}
        <div className="p-6 pb-4 border-b border-white/[0.06]">
          <div className="flex items-center gap-4">
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center"
              style={{
                background: "linear-gradient(135deg, #7c3aed, #a855f7)",
              }}
            >
              <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div>
              <h2 className="text-white font-bold text-xl">3D Vector Graph</h2>
              <p className="text-slate-400 text-sm mt-0.5">
                연구 질문을 입력하면 3D 벡터 공간에서 시각화합니다
              </p>
            </div>
          </div>
        </div>

        {/* Input Form */}
        <form onSubmit={handleSubmit} className="p-6">
          <div className="relative">
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="연구 질문을 입력하세요... (예: NSCLC 면역요법의 최신 동향)"
              className="w-full px-4 py-4 rounded-xl text-base text-white placeholder-slate-500 outline-none resize-none"
              style={{
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(255,255,255,0.08)",
                minHeight: "100px",
              }}
              disabled={isProcessing}
              autoFocus
            />
            <button
              type="submit"
              disabled={!question.trim() || isProcessing}
              className="absolute bottom-4 right-4 px-5 py-2.5 rounded-lg text-white text-sm font-bold flex items-center gap-2 transition-all hover:scale-105 disabled:opacity-50 disabled:hover:scale-100"
              style={{
                background: "linear-gradient(135deg, #7c3aed, #a855f7)",
                boxShadow: "0 4px 16px rgba(124,58,237,0.4)",
              }}
            >
              {isProcessing ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  분석 중
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  시각화
                </>
              )}
            </button>
          </div>
        </form>

        {/* Example Questions */}
        <div className="px-6 pb-6">
          <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-3">
            예시 질문
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {EXAMPLE_QUESTIONS.map((category) => (
              <div key={category.category}>
                <div className="text-xs text-purple-400 font-medium mb-2">
                  {category.category}
                </div>
                <div className="space-y-1.5">
                  {category.questions.slice(0, 2).map((q) => (
                    <button
                      key={q}
                      onClick={() => handleExampleClick(q)}
                      className="w-full text-left px-3 py-2 rounded-lg text-xs text-slate-400 hover:text-white transition-all hover:bg-white/5"
                      style={{
                        background: "rgba(255,255,255,0.02)",
                        border: "1px solid rgba(255,255,255,0.05)",
                      }}
                    >
                      {q.length > 35 ? q.slice(0, 35) + "..." : q}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer hint */}
        <div className="px-6 pb-4 text-center">
          <p className="text-slate-600 text-xs">
            Enter를 누르거나 시각화 버튼을 클릭하세요
          </p>
        </div>
      </div>
    </div>
  );
}

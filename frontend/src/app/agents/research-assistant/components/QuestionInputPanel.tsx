"use client";

import { useState } from "react";
import { Send, Sparkles, X, Loader2 } from "lucide-react";
import { EXAMPLE_QUESTIONS } from "../constants";

interface QuestionInputPanelProps {
  onSubmit: (question: string) => void;
  isProcessing: boolean;
  onClose: () => void;
}

export default function QuestionInputPanel({
  onSubmit,
  isProcessing,
  onClose,
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
    <div
      className="absolute bottom-6 left-1/2 -translate-x-1/2 z-[220] w-full max-w-3xl px-4"
      style={{ animation: "fadeSlideUp 0.4s ease-out" }}
    >
      <style jsx>{`
        @keyframes fadeSlideUp {
          from {
            opacity: 0;
            transform: translateX(-50%) translateY(12px);
          }
          to {
            opacity: 1;
            transform: translateX(-50%) translateY(0);
          }
        }
      `}</style>

      <div
        className="rounded-2xl overflow-hidden shadow-2xl"
        style={{
          background: "rgba(10, 14, 26, 0.92)",
          backdropFilter: "blur(24px)",
          border: "1px solid rgba(255, 255, 255, 0.1)",
        }}
      >
        {/* Header */}
        <div className="p-4 pb-3 border-b border-white/[0.06] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center"
              style={{
                background: "linear-gradient(135deg, #2563eb, #7c3aed)",
              }}
            >
              <Sparkles size={16} className="text-white" />
            </div>
            <div>
              <h3 className="text-white font-bold text-sm">Research Query</h3>
              <p className="text-slate-500 text-[10px]">
                Vector-Based 3D Reasoning Engine
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/10 transition-all"
          >
            <X size={16} />
          </button>
        </div>

        {/* Input Form */}
        <form onSubmit={handleSubmit} className="p-4">
          <div className="relative">
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="연구 질문을 입력하세요... (예: NSCLC 면역요법의 최신 동향)"
              className="w-full px-4 py-3 pr-24 rounded-xl text-sm text-white placeholder-slate-500 outline-none resize-none"
              style={{
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(255,255,255,0.08)",
                minHeight: "80px",
              }}
              disabled={isProcessing}
            />
            <button
              type="submit"
              disabled={!question.trim() || isProcessing}
              className="absolute bottom-3 right-3 px-4 py-2 rounded-lg text-white text-xs font-bold flex items-center gap-2 transition-all hover:scale-105 disabled:opacity-50 disabled:hover:scale-100"
              style={{
                background: "linear-gradient(135deg, #2563eb, #7c3aed)",
                boxShadow: "0 4px 12px rgba(37,99,235,0.3)",
              }}
            >
              {isProcessing ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  분석 중
                </>
              ) : (
                <>
                  <Send size={14} />
                  분석
                </>
              )}
            </button>
          </div>
        </form>

        {/* Example Questions */}
        <div className="px-4 pb-4">
          <div className="text-[9px] font-bold text-slate-500 uppercase tracking-[0.1em] mb-2">
            Quick Examples
          </div>
          <div className="flex flex-wrap gap-2">
            {EXAMPLE_QUESTIONS.flatMap((cat) =>
              cat.questions.slice(0, 1).map((q) => (
                <button
                  key={q}
                  onClick={() => handleExampleClick(q)}
                  className="px-3 py-1.5 rounded-lg text-[11px] text-slate-400 hover:text-white transition-all hover:bg-white/5"
                  style={{
                    background: "rgba(255,255,255,0.03)",
                    border: "1px solid rgba(255,255,255,0.06)",
                  }}
                >
                  {q.length > 40 ? q.slice(0, 40) + "..." : q}
                </button>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

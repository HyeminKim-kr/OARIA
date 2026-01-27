"use client";

import { Loader2, FlaskConical, ChevronUp, ChevronDown, Brain } from "lucide-react";

interface HypothesisFormProps {
  hypothesis: string;
  onHypothesisChange: (value: string) => void;
  researchContext: string;
  onResearchContextChange: (value: string) => void;
  showAdvanced: boolean;
  onToggleAdvanced: () => void;
  isLoading: boolean;
  onSubmit: (e: React.FormEvent) => void;
}

export function HypothesisForm({
  hypothesis,
  onHypothesisChange,
  researchContext,
  onResearchContextChange,
  showAdvanced,
  onToggleAdvanced,
  isLoading,
  onSubmit,
}: HypothesisFormProps) {
  return (
    <div className="bg-[var(--background)] border-2 border-[var(--oaria-border-strong)] rounded-2xl p-6 mb-8">
      <form onSubmit={onSubmit}>
        {/* 에이전트 정보 배지 */}
        <div className="mb-6 flex items-center gap-2 px-3 py-2 rounded-lg bg-purple-500/10 border border-purple-500/20 w-fit">
          <Brain size={16} className="text-purple-500" />
          <span className="text-sm font-medium text-purple-600 dark:text-purple-400">
            ReAct 자율 에이전트
          </span>
          <span className="text-xs text-purple-500/70">
            LLM이 스스로 판단하며 실험 계획 수립
          </span>
        </div>

        {/* 가설 입력 */}
        <div className="mb-4">
          <label className="block font-[family-name:var(--font-outfit)] text-sm font-medium mb-2">
            검증하고자 하는 가설 *
          </label>
          <textarea
            value={hypothesis}
            onChange={(e) => onHypothesisChange(e.target.value)}
            placeholder="예: EGFR T790M 돌연변이 환자에서 osimertinib 내성 기전으로 MET amplification이 관여한다"
            rows={3}
            disabled={isLoading}
            className="w-full px-4 py-3 rounded-xl border-2 border-[var(--oaria-border)] bg-[var(--background)] font-[family-name:var(--font-dm-sans)] text-base focus:border-[var(--oaria-teal)] focus:ring-2 focus:ring-[var(--oaria-teal)]/20 outline-none transition-all resize-none placeholder:text-[var(--oaria-tagline)] disabled:opacity-50"
          />
        </div>

        {/* 고급 옵션 토글 */}
        <button
          type="button"
          onClick={onToggleAdvanced}
          className="flex items-center gap-2 text-sm text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] mb-4"
        >
          {showAdvanced ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          고급 옵션
        </button>

        {/* 고급 옵션 */}
        {showAdvanced && (
          <div className="mb-4 p-4 rounded-xl bg-[var(--oaria-border)]/20 space-y-4">
            <div>
              <label className="block font-[family-name:var(--font-outfit)] text-sm font-medium mb-2">
                연구 맥락 (선택)
              </label>
              <input
                type="text"
                value={researchContext}
                onChange={(e) => onResearchContextChange(e.target.value)}
                placeholder="예: NSCLC targeted therapy resistance research"
                disabled={isLoading}
                className="w-full px-4 py-2 rounded-lg border border-[var(--oaria-border)] bg-[var(--background)] font-[family-name:var(--font-dm-sans)] text-sm focus:border-[var(--oaria-teal)] outline-none transition-all placeholder:text-[var(--oaria-tagline)] disabled:opacity-50"
              />
            </div>
          </div>
        )}

        {/* 제출 버튼 */}
        <button
          type="submit"
          disabled={!hypothesis.trim() || isLoading}
          className="w-full py-3 rounded-xl bg-[var(--oaria-teal)] text-white font-[family-name:var(--font-dm-sans)] font-medium hover:bg-[var(--oaria-light-teal)] disabled:bg-[var(--oaria-border)] disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
        >
          {isLoading ? (
            <>
              <Loader2 size={20} className="animate-spin" />
              실험 계획 생성 중...
            </>
          ) : (
            <>
              <FlaskConical size={20} />
              실험 계획 생성
            </>
          )}
        </button>
      </form>
    </div>
  );
}

"use client";

import { useState } from "react";
import { X, Check, AlertTriangle, Clock, DollarSign, FileCheck } from "lucide-react";

interface ApprovalChoice {
  choice_id: string;
  label: string;
  description: string;
  estimated_cost?: string;
  estimated_timeline?: string;
}

interface ApprovalModalProps {
  isOpen: boolean;
  onClose: () => void;
  onApprove: (decision: Record<string, unknown>) => Promise<void>;
  jobName?: string;
  gateId?: string;
  choices?: ApprovalChoice[];
  isLoading?: boolean;
}

export function ApprovalModal({
  isOpen,
  onClose,
  onApprove,
  jobName,
  gateId,
  choices = [],
  isLoading = false,
}: ApprovalModalProps) {
  const [selectedChoice, setSelectedChoice] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleApprove = async () => {
    if (!selectedChoice && choices.length > 0) return;

    setIsSubmitting(true);
    try {
      await onApprove({
        choice_id: selectedChoice,
        comment: comment.trim() || undefined,
        approved_at: new Date().toISOString(),
      });
      onClose();
    } catch (error) {
      console.error("Approval failed:", error);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div
        className="bg-[var(--background)] rounded-2xl max-w-lg w-full max-h-[80vh] overflow-hidden shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-[var(--oaria-border)] flex items-center justify-between bg-yellow-50">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-yellow-100 text-yellow-600">
              <FileCheck size={20} />
            </div>
            <div>
              <h3 className="font-[family-name:var(--font-outfit)] font-semibold">
                승인 필요
              </h3>
              {jobName && (
                <p className="text-xs text-[var(--oaria-text-secondary)]">
                  {jobName}
                </p>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isSubmitting}
            className="p-2 hover:bg-[var(--oaria-border)] rounded-lg transition-colors disabled:opacity-50"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-4 overflow-y-auto max-h-[50vh]">
          {/* Gate Info */}
          {gateId && (
            <div className="mb-4 p-3 rounded-lg bg-[var(--oaria-border)]/30">
              <div className="flex items-center gap-2 text-sm">
                <AlertTriangle size={16} className="text-yellow-600" />
                <span className="font-medium">승인 게이트: {gateId}</span>
              </div>
              <p className="text-xs text-[var(--oaria-text-secondary)] mt-1">
                이 작업은 고비용 실험 또는 윤리 심의가 필요한 항목을 포함합니다.
              </p>
            </div>
          )}

          {/* Choices */}
          {choices.length > 0 ? (
            <div className="space-y-3">
              <p className="text-sm font-medium">옵션을 선택하세요:</p>
              {choices.map((choice) => (
                <button
                  key={choice.choice_id}
                  onClick={() => setSelectedChoice(choice.choice_id)}
                  disabled={isSubmitting}
                  className={`w-full p-4 rounded-xl border-2 text-left transition-all ${
                    selectedChoice === choice.choice_id
                      ? "border-[var(--oaria-teal)] bg-[var(--oaria-teal)]/10"
                      : "border-[var(--oaria-border)] hover:border-[var(--oaria-teal)]/50"
                  } disabled:opacity-50`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1">
                      <p className="font-medium">{choice.label}</p>
                      <p className="text-sm text-[var(--oaria-text-secondary)] mt-1">
                        {choice.description}
                      </p>
                    </div>
                    {selectedChoice === choice.choice_id && (
                      <Check size={20} className="text-[var(--oaria-teal)] flex-shrink-0" />
                    )}
                  </div>

                  {/* Cost & Timeline */}
                  {(choice.estimated_cost || choice.estimated_timeline) && (
                    <div className="flex items-center gap-4 mt-3 pt-3 border-t border-[var(--oaria-border)]">
                      {choice.estimated_cost && (
                        <div className="flex items-center gap-1 text-xs text-[var(--oaria-text-secondary)]">
                          <DollarSign size={12} />
                          <span>{choice.estimated_cost}</span>
                        </div>
                      )}
                      {choice.estimated_timeline && (
                        <div className="flex items-center gap-1 text-xs text-[var(--oaria-text-secondary)]">
                          <Clock size={12} />
                          <span>{choice.estimated_timeline}</span>
                        </div>
                      )}
                    </div>
                  )}
                </button>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <p className="text-[var(--oaria-text-secondary)]">
                이 작업을 승인하시겠습니까?
              </p>
            </div>
          )}

          {/* Comment */}
          <div className="mt-4">
            <label className="block text-sm font-medium mb-2">
              코멘트 (선택)
            </label>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="승인에 대한 코멘트를 남겨주세요..."
              rows={2}
              disabled={isSubmitting}
              className="w-full px-3 py-2 rounded-lg border border-[var(--oaria-border)] bg-[var(--background)] text-sm focus:border-[var(--oaria-teal)] outline-none transition-all resize-none placeholder:text-[var(--oaria-tagline)] disabled:opacity-50"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-[var(--oaria-border)] flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            disabled={isSubmitting}
            className="px-4 py-2 rounded-lg border border-[var(--oaria-border)] text-sm font-medium hover:bg-[var(--oaria-border)]/50 transition-colors disabled:opacity-50"
          >
            취소
          </button>
          <button
            onClick={handleApprove}
            disabled={isSubmitting || isLoading || (choices.length > 0 && !selectedChoice)}
            className="px-4 py-2 rounded-lg bg-[var(--oaria-teal)] text-white text-sm font-medium hover:bg-[#0B7A70] transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {isSubmitting ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                처리 중...
              </>
            ) : (
              <>
                <Check size={16} />
                승인
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

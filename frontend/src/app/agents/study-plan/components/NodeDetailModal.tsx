"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  X,
  CheckCircle2,
  Lightbulb,
  AlertTriangle,
} from "lucide-react";
import type {
  NodeProgress,
  NodeDetailData,
  HypothesisData,
  TestQuestion,
  Experiment,
} from "../types";

interface NodeDetailModalProps {
  nodeId: string;
  nodes: NodeProgress[];
  nodeDetails: NodeDetailData;
  onClose: () => void;
}

export function NodeDetailModal({
  nodeId,
  nodes,
  nodeDetails,
  onClose,
}: NodeDetailModalProps) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const details = nodeDetails as Record<string, any>;
  const nodeData = details[nodeId];
  const node = nodes.find((n) => n.id === nodeId);

  if (!node) return null;

  return (
    <div
      className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-[var(--background)] rounded-2xl max-w-2xl w-full max-h-[80vh] overflow-hidden shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-[var(--oaria-border)] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className={`p-2 rounded-lg ${
                node.status === "completed"
                  ? "bg-green-100 text-green-600"
                  : node.status === "active"
                  ? "bg-[var(--oaria-teal)]/20 text-[var(--oaria-teal)]"
                  : "bg-[var(--oaria-border)] text-[var(--oaria-text-secondary)]"
              }`}
            >
              {node.icon}
            </div>
            <div>
              <h3 className="font-[family-name:var(--font-outfit)] font-semibold">
                {node.label}
              </h3>
              <p className="text-xs text-[var(--oaria-text-secondary)]">
                {node.description}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-[var(--oaria-border)] rounded-lg transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-4 overflow-y-auto max-h-[60vh]">
          {!nodeData ? (
            <div className="text-center py-8 text-[var(--oaria-text-secondary)]">
              {node.status === "completed" ? (
                <>
                  <CheckCircle2
                    size={32}
                    className="mx-auto mb-2 text-green-500"
                  />
                  <p>이 단계가 완료되었습니다</p>
                  <p className="text-xs mt-1 opacity-70">
                    상세 정보는 최종 계획서에서 확인하세요
                  </p>
                </>
              ) : (
                <>
                  <Lightbulb size={32} className="mx-auto mb-2 opacity-50" />
                  <p>아직 이 단계가 실행되지 않았습니다</p>
                </>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              {/* 가설 파싱 */}
              {nodeId === "parse_hypothesis" && nodeData.hypothesis && (
                <>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-medium px-2 py-1 rounded bg-[var(--oaria-teal)]/20 text-[var(--oaria-teal)]">
                      신뢰도: {((nodeData.confidence as number) * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-3 rounded-lg bg-blue-50 border border-blue-200">
                      <span className="text-xs text-blue-600 font-medium">
                        독립 변수
                      </span>
                      <p className="font-[family-name:var(--font-dm-sans)] text-blue-900">
                        {(nodeData.hypothesis as HypothesisData).independent_variable}
                      </p>
                    </div>
                    <div className="p-3 rounded-lg bg-orange-50 border border-orange-200">
                      <span className="text-xs text-orange-600 font-medium">
                        종속 변수
                      </span>
                      <p className="font-[family-name:var(--font-dm-sans)] text-orange-900">
                        {(nodeData.hypothesis as HypothesisData).dependent_variable}
                      </p>
                    </div>
                  </div>
                  {(nodeData.hypothesis as HypothesisData).population && (
                    <div className="p-3 rounded-lg bg-[var(--oaria-border)]/30">
                      <span className="text-xs text-[var(--oaria-text-secondary)]">
                        대상 집단
                      </span>
                      <p className="font-[family-name:var(--font-dm-sans)]">
                        {(nodeData.hypothesis as HypothesisData).population}
                      </p>
                    </div>
                  )}
                </>
              )}

              {/* 검증 질문 */}
              {nodeId === "decompose_tests" && nodeData.test_questions && (
                <div className="space-y-3">
                  {(nodeData.test_questions as TestQuestion[]).map((tq, i) => (
                    <div
                      key={i}
                      className="p-3 rounded-lg bg-[var(--oaria-border)]/30"
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <span
                          className={`px-2 py-0.5 rounded text-xs font-medium ${
                            tq.category === "necessity"
                              ? "bg-blue-100 text-blue-700"
                              : tq.category === "sufficiency"
                              ? "bg-green-100 text-green-700"
                              : tq.category === "epistasis"
                              ? "bg-orange-100 text-orange-700"
                              : "bg-purple-100 text-purple-700"
                          }`}
                        >
                          {tq.category.toUpperCase()}
                        </span>
                      </div>
                      <p className="font-[family-name:var(--font-dm-sans)] text-sm mb-2">
                        {tq.question}
                      </p>
                      <p className="text-xs text-[var(--oaria-text-secondary)] italic">
                        판정 기준: {tq.decision_rule}
                      </p>
                    </div>
                  ))}
                </div>
              )}

              {/* 검색 결과 */}
              {nodeId === "search_studies" && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-4 rounded-lg bg-[var(--oaria-teal)]/10 text-center">
                      <p className="text-3xl font-bold text-[var(--oaria-teal)]">
                        {nodeData.study_count || 0}
                      </p>
                      <p className="text-xs text-[var(--oaria-text-secondary)]">
                        관련 논문
                      </p>
                    </div>
                    <div className="p-4 rounded-lg bg-green-50 text-center">
                      <p className="text-3xl font-bold text-green-600">
                        {(((nodeData.coverage as number) || 0) * 100).toFixed(0)}%
                      </p>
                      <p className="text-xs text-[var(--oaria-text-secondary)]">
                        커버리지
                      </p>
                    </div>
                  </div>
                  {nodeData.gaps && (nodeData.gaps as string[]).length > 0 && (
                    <div>
                      <p className="text-xs text-[var(--oaria-text-secondary)] mb-2">
                        커버리지 부족 영역
                      </p>
                      <ul className="space-y-1">
                        {(nodeData.gaps as string[]).map((gap, i) => (
                          <li
                            key={i}
                            className="text-sm text-orange-600 flex items-start gap-2"
                          >
                            <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                            {gap}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {/* Evidence Pack */}
              {nodeId === "build_evidence" && (
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 rounded-lg bg-purple-50 text-center">
                    <p className="text-3xl font-bold text-purple-600">
                      {nodeData.snippet_count || 0}
                    </p>
                    <p className="text-xs text-[var(--oaria-text-secondary)]">
                      스니펫
                    </p>
                  </div>
                  <div className="p-4 rounded-lg bg-indigo-50 text-center">
                    <p className="text-3xl font-bold text-indigo-600">
                      {nodeData.pack_count || 0}
                    </p>
                    <p className="text-xs text-[var(--oaria-text-secondary)]">
                      Evidence Pack
                    </p>
                  </div>
                </div>
              )}

              {/* 실험 설계 */}
              {nodeId === "design_experiments" && nodeData.experiments && (
                <div className="space-y-3">
                  {(nodeData.experiments as Experiment[]).map((exp) => (
                    <div
                      key={exp.id}
                      className="p-3 rounded-lg border border-[var(--oaria-border)]"
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <span
                          className={`px-2 py-0.5 rounded text-xs font-medium ${
                            exp.type === "in_vitro"
                              ? "bg-blue-100 text-blue-700"
                              : exp.type === "in_vivo"
                              ? "bg-green-100 text-green-700"
                              : exp.type === "clinical"
                              ? "bg-red-100 text-red-700"
                              : "bg-gray-100 text-gray-700"
                          }`}
                        >
                          {exp.type.replace("_", " ").toUpperCase()}
                        </span>
                        <span className="text-xs text-[var(--oaria-text-secondary)]">
                          {exp.test_category}
                        </span>
                      </div>
                      <p className="font-[family-name:var(--font-dm-sans)] font-medium">
                        {exp.title}
                      </p>
                    </div>
                  ))}
                </div>
              )}

              {/* Critique */}
              {nodeId === "critique_refine" && (
                <div className="space-y-4">
                  <div className="flex items-center gap-4">
                    <div
                      className={`p-4 rounded-lg flex-1 text-center ${
                        (nodeData.quality_score as number) >= 0.8
                          ? "bg-green-50"
                          : "bg-yellow-50"
                      }`}
                    >
                      <p
                        className={`text-3xl font-bold ${
                          (nodeData.quality_score as number) >= 0.8
                            ? "text-green-600"
                            : "text-yellow-600"
                        }`}
                      >
                        {(((nodeData.quality_score as number) || 0) * 100).toFixed(0)}%
                      </p>
                      <p className="text-xs text-[var(--oaria-text-secondary)]">
                        품질 점수
                      </p>
                    </div>
                    <div
                      className={`p-4 rounded-lg flex-1 text-center ${
                        nodeData.passed ? "bg-green-50" : "bg-orange-50"
                      }`}
                    >
                      <p
                        className={`text-lg font-bold ${
                          nodeData.passed ? "text-green-600" : "text-orange-600"
                        }`}
                      >
                        {nodeData.passed
                          ? "통과"
                          : `수정 ${nodeData.revision_count || 0}회`}
                      </p>
                      <p className="text-xs text-[var(--oaria-text-secondary)]">
                        상태
                      </p>
                    </div>
                  </div>
                  {nodeData.suggestions &&
                    (nodeData.suggestions as string[]).length > 0 && (
                      <div>
                        <p className="text-xs text-[var(--oaria-text-secondary)] mb-2">
                          개선 제안
                        </p>
                        <ul className="space-y-1">
                          {(nodeData.suggestions as string[])
                            .slice(0, 3)
                            .map((s, i) => (
                              <li
                                key={i}
                                className="text-sm flex items-start gap-2"
                              >
                                <Lightbulb
                                  size={14}
                                  className="mt-0.5 shrink-0 text-yellow-500"
                                />
                                {s}
                              </li>
                            ))}
                        </ul>
                      </div>
                    )}
                </div>
              )}

              {/* 측정 항목 */}
              {nodeId === "identify_measurements" && (
                <div className="space-y-4">
                  <div className="p-4 rounded-lg bg-[var(--oaria-teal)]/10 text-center">
                    <p className="text-3xl font-bold text-[var(--oaria-teal)]">
                      {nodeData.measurement_count || 0}
                    </p>
                    <p className="text-xs text-[var(--oaria-text-secondary)]">
                      측정 항목
                    </p>
                  </div>
                  {nodeData.priority &&
                    (nodeData.priority as string[]).length > 0 && (
                      <div>
                        <p className="text-xs text-[var(--oaria-text-secondary)] mb-2">
                          우선순위
                        </p>
                        <ol className="list-decimal list-inside space-y-1">
                          {(nodeData.priority as string[]).map((p, i) => (
                            <li key={i} className="text-sm">
                              {p}
                            </li>
                          ))}
                        </ol>
                      </div>
                    )}
                </div>
              )}

              {/* 실현가능성 */}
              {nodeId === "validate_feasibility" && (
                <div className="space-y-4">
                  <div className="p-4 rounded-lg bg-[var(--oaria-teal)]/10 text-center">
                    <p className="text-3xl font-bold text-[var(--oaria-teal)]">
                      {(((nodeData.overall_score as number) || 0) * 100).toFixed(0)}%
                    </p>
                    <p className="text-xs text-[var(--oaria-text-secondary)]">
                      실현가능성 점수
                    </p>
                  </div>
                  {nodeData.concerns &&
                    (nodeData.concerns as string[]).length > 0 && (
                      <div>
                        <p className="text-xs text-[var(--oaria-text-secondary)] mb-2">
                          우려 사항
                        </p>
                        <ul className="space-y-1">
                          {(nodeData.concerns as string[]).map((c, i) => (
                            <li
                              key={i}
                              className="text-sm text-orange-600 flex items-start gap-2"
                            >
                              <AlertTriangle
                                size={14}
                                className="mt-0.5 shrink-0"
                              />
                              {c}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                </div>
              )}

              {/* 승인 게이트 */}
              {nodeId === "approval_gate" && (
                <div className="space-y-4">
                  <div
                    className={`p-4 rounded-lg text-center ${
                      nodeData.approval_required ? "bg-orange-50" : "bg-green-50"
                    }`}
                  >
                    <p
                      className={`text-lg font-bold ${
                        nodeData.approval_required
                          ? "text-orange-600"
                          : "text-green-600"
                      }`}
                    >
                      {nodeData.approval_required ? "승인 필요" : "승인 불필요"}
                    </p>
                    {nodeData.item_count && (
                      <p className="text-xs text-[var(--oaria-text-secondary)]">
                        {nodeData.item_count}개 항목 검토 필요
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* 최종 계획 */}
              {nodeId === "synthesize_plan" && nodeData.final_plan && (
                <div className="space-y-4">
                  {nodeData.executive_summary && (
                    <div className="p-4 rounded-lg bg-[var(--oaria-teal)]/10 border border-[var(--oaria-teal)]/20">
                      <h4 className="font-[family-name:var(--font-outfit)] font-medium text-[var(--oaria-teal)] mb-2">
                        Executive Summary
                      </h4>
                      <p className="text-sm">{nodeData.executive_summary as string}</p>
                    </div>
                  )}
                  <div className="text-sm leading-relaxed max-h-[300px] overflow-y-auto prose prose-sm max-w-none prose-headings:font-semibold prose-headings:text-[var(--foreground)] prose-p:text-[var(--foreground)] prose-strong:text-[var(--foreground)] prose-li:text-[var(--foreground)] prose-table:text-sm prose-th:bg-[var(--oaria-border)]/50 prose-th:px-2 prose-th:py-1 prose-td:px-2 prose-td:py-1 prose-td:border prose-td:border-[var(--oaria-border)] prose-th:border prose-th:border-[var(--oaria-border)]">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {nodeData.final_plan as string}
                    </ReactMarkdown>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

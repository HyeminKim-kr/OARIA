"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  FileText,
  FlaskConical,
  BookOpen,
  BarChart3,
  Download,
  Copy,
  Check,
  Beaker,
  TestTube,
  Microscope,
  Users,
  Clock,
  DollarSign,
  Sparkles,
} from "lucide-react";

interface ResultsPanelProps {
  finalPlan: string;
  executiveSummary?: string;
  planA?: string;
  planB?: string;
  experimentCount?: number;
  totalDuration?: number;
  nodeDetails?: Record<string, unknown>;
}

type TabId = "summary" | "experiments" | "evidence" | "full";

interface Tab {
  id: TabId;
  label: string;
  icon: React.ReactNode;
}

const tabs: Tab[] = [
  { id: "summary", label: "요약", icon: <BarChart3 size={16} /> },
  { id: "experiments", label: "실험 설계", icon: <FlaskConical size={16} /> },
  { id: "evidence", label: "근거 자료", icon: <BookOpen size={16} /> },
  { id: "full", label: "전체 계획서", icon: <FileText size={16} /> },
];

export function ResultsPanel({
  finalPlan,
  executiveSummary,
  planA,
  planB,
  experimentCount = 0,
  totalDuration = 0,
  nodeDetails = {},
}: ResultsPanelProps) {
  const [activeTab, setActiveTab] = useState<TabId>("summary");
  const [copied, setCopied] = useState(false);
  const [showPlanB, setShowPlanB] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(finalPlan);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const blob = new Blob([finalPlan], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `study-plan-${new Date().toISOString().split("T")[0]}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Extract experiments from nodeDetails
  const experiments = (nodeDetails.design_experiments as Record<string, unknown>)?.experiments as Array<{
    type: string;
    title: string;
    objective?: string;
    estimated_cost_level?: string;
  }> || [];

  // Extract evidence from nodeDetails
  const evidenceSnippets = Number((nodeDetails.build_evidence as Record<string, unknown>)?.snippet_count) || 0;
  const evidencePacks = Number((nodeDetails.build_evidence as Record<string, unknown>)?.pack_count) || 0;

  const getExperimentIcon = (type: string) => {
    switch (type?.toLowerCase()) {
      case "in_vitro":
        return <TestTube size={18} className="text-blue-500" />;
      case "in_vivo":
        return <Beaker size={18} className="text-green-500" />;
      case "clinical":
        return <Users size={18} className="text-purple-500" />;
      default:
        return <Microscope size={18} className="text-gray-500" />;
    }
  };

  const getExperimentTypeBadge = (type: string) => {
    const colors: Record<string, string> = {
      in_vitro: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
      in_vivo: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
      clinical: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
      computational: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
    };
    return colors[type?.toLowerCase()] || "bg-gray-100 text-gray-700";
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-[var(--background)] border-2 border-[var(--oaria-teal)]/30 rounded-2xl overflow-hidden shadow-xl shadow-[var(--oaria-teal)]/5"
    >
      {/* Header with Success Animation */}
      <div className="relative bg-gradient-to-r from-[var(--oaria-teal)]/20 to-green-500/20 p-6">
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: "spring", stiffness: 200 }}
          className="absolute top-4 right-4"
        >
          <div className="w-12 h-12 rounded-full bg-green-500 flex items-center justify-center">
            <Check size={24} className="text-white" />
          </div>
        </motion.div>

        <div className="flex items-center gap-3 mb-4">
          <Sparkles size={24} className="text-[var(--oaria-teal)]" />
          <h2 className="text-xl font-bold">실험 계획서 생성 완료</h2>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-white/50 dark:bg-black/20 rounded-xl p-3">
            <div className="flex items-center gap-2 text-[var(--oaria-teal)]">
              <FlaskConical size={18} />
              <span className="text-2xl font-bold">{experimentCount}</span>
            </div>
            <p className="text-xs text-[var(--oaria-text-secondary)] mt-1">실험 설계</p>
          </div>
          <div className="bg-white/50 dark:bg-black/20 rounded-xl p-3">
            <div className="flex items-center gap-2 text-blue-500">
              <BookOpen size={18} />
              <span className="text-2xl font-bold">{evidencePacks}</span>
            </div>
            <p className="text-xs text-[var(--oaria-text-secondary)] mt-1">참고 논문</p>
          </div>
          <div className="bg-white/50 dark:bg-black/20 rounded-xl p-3">
            <div className="flex items-center gap-2 text-purple-500">
              <Clock size={18} />
              <span className="text-2xl font-bold">{(totalDuration / 1000).toFixed(1)}s</span>
            </div>
            <p className="text-xs text-[var(--oaria-text-secondary)] mt-1">소요 시간</p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-[var(--oaria-border)]">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`
              flex-1 flex items-center justify-center gap-2 py-3 text-sm font-medium transition-all
              ${activeTab === tab.id
                ? "text-[var(--oaria-teal)] border-b-2 border-[var(--oaria-teal)] bg-[var(--oaria-teal)]/5"
                : "text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] hover:bg-[var(--oaria-border)]/30"
              }
            `}
          >
            {tab.icon}
            <span className="hidden sm:inline">{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="p-6">
        <AnimatePresence mode="wait">
          {/* Summary Tab */}
          {activeTab === "summary" && (
            <motion.div
              key="summary"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              className="space-y-4"
            >
              {executiveSummary && (
                <div className="p-4 rounded-xl bg-[var(--oaria-teal)]/5 border border-[var(--oaria-teal)]/20">
                  <h3 className="font-semibold text-[var(--oaria-teal)] mb-2 flex items-center gap-2">
                    <BarChart3 size={18} />
                    Executive Summary
                  </h3>
                  <p className="text-sm leading-relaxed">{executiveSummary}</p>
                </div>
              )}

              {/* Plan A/B Toggle */}
              {planA && planB && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setShowPlanB(false)}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                        !showPlanB
                          ? "bg-green-500 text-white"
                          : "bg-[var(--oaria-border)] hover:bg-[var(--oaria-border)]/80"
                      }`}
                    >
                      Plan A (이상적)
                    </button>
                    <button
                      onClick={() => setShowPlanB(true)}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                        showPlanB
                          ? "bg-blue-500 text-white"
                          : "bg-[var(--oaria-border)] hover:bg-[var(--oaria-border)]/80"
                      }`}
                    >
                      Plan B (현실적)
                    </button>
                  </div>

                  <AnimatePresence mode="wait">
                    <motion.div
                      key={showPlanB ? "planB" : "planA"}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                      className={`p-4 rounded-xl border ${
                        showPlanB
                          ? "bg-blue-50 dark:bg-blue-900/10 border-blue-200 dark:border-blue-800"
                          : "bg-green-50 dark:bg-green-900/10 border-green-200 dark:border-green-800"
                      }`}
                    >
                      <div className="prose prose-sm max-w-none dark:prose-invert">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {showPlanB ? planB : planA}
                        </ReactMarkdown>
                      </div>
                    </motion.div>
                  </AnimatePresence>
                </div>
              )}
            </motion.div>
          )}

          {/* Experiments Tab */}
          {activeTab === "experiments" && (
            <motion.div
              key="experiments"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              className="space-y-3"
            >
              {experiments.length > 0 ? (
                experiments.map((exp, index) => (
                  <motion.div
                    key={index}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.1 }}
                    className="p-4 rounded-xl border border-[var(--oaria-border)] hover:border-[var(--oaria-teal)]/30 hover:shadow-lg transition-all"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-3">
                        <div className="mt-1">{getExperimentIcon(exp.type)}</div>
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${getExperimentTypeBadge(exp.type)}`}>
                              {exp.type?.replace("_", " ").toUpperCase()}
                            </span>
                          </div>
                          <h4 className="font-medium text-sm">{exp.title}</h4>
                          {exp.objective && (
                            <p className="text-xs text-[var(--oaria-text-secondary)] mt-1">
                              {exp.objective}
                            </p>
                          )}
                        </div>
                      </div>
                      {exp.estimated_cost_level && (
                        <span className="flex items-center gap-1 text-xs text-[var(--oaria-text-secondary)]">
                          <DollarSign size={12} />
                          {exp.estimated_cost_level}
                        </span>
                      )}
                    </div>
                  </motion.div>
                ))
              ) : (
                <div className="text-center py-8 text-[var(--oaria-text-secondary)]">
                  <FlaskConical size={32} className="mx-auto mb-2 opacity-50" />
                  <p className="text-sm">전체 계획서에서 실험 설계를 확인하세요</p>
                </div>
              )}
            </motion.div>
          )}

          {/* Evidence Tab */}
          {activeTab === "evidence" && (
            <motion.div
              key="evidence"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              className="space-y-4"
            >
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 rounded-xl bg-blue-500/10 border border-blue-500/20">
                  <div className="flex items-center gap-2 text-blue-500 mb-2">
                    <BookOpen size={20} />
                    <span className="text-2xl font-bold">{evidencePacks}</span>
                  </div>
                  <p className="text-xs text-[var(--oaria-text-secondary)]">참고 논문</p>
                </div>
                <div className="p-4 rounded-xl bg-purple-500/10 border border-purple-500/20">
                  <div className="flex items-center gap-2 text-purple-500 mb-2">
                    <FileText size={20} />
                    <span className="text-2xl font-bold">{evidenceSnippets}</span>
                  </div>
                  <p className="text-xs text-[var(--oaria-text-secondary)]">근거 스니펫</p>
                </div>
              </div>
              <p className="text-sm text-[var(--oaria-text-secondary)] text-center">
                상세 근거 자료는 전체 계획서에서 확인할 수 있습니다.
              </p>
            </motion.div>
          )}

          {/* Full Plan Tab */}
          {activeTab === "full" && (
            <motion.div
              key="full"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
            >
              {/* Actions */}
              <div className="flex items-center gap-2 mb-4">
                <button
                  onClick={handleCopy}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[var(--oaria-border)] hover:bg-[var(--oaria-border)]/80 text-sm transition-colors"
                >
                  {copied ? <Check size={14} /> : <Copy size={14} />}
                  {copied ? "복사됨" : "복사"}
                </button>
                <button
                  onClick={handleDownload}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[var(--oaria-border)] hover:bg-[var(--oaria-border)]/80 text-sm transition-colors"
                >
                  <Download size={14} />
                  다운로드
                </button>
              </div>

              {/* Markdown Content */}
              <div className="prose prose-sm max-w-none dark:prose-invert prose-headings:font-semibold prose-table:text-sm prose-th:bg-[var(--oaria-border)]/50 prose-th:px-3 prose-th:py-2 prose-td:px-3 prose-td:py-2 prose-td:border prose-td:border-[var(--oaria-border)] prose-th:border prose-th:border-[var(--oaria-border)] max-h-[500px] overflow-y-auto">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{finalPlan}</ReactMarkdown>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

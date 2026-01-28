"use client";

import { motion } from "framer-motion";
import {
  Microscope,
  HelpCircle,
  FlaskConical,
  Gauge,
  FileText,
  CheckCircle2,
  AlertCircle,
  BookOpen,
} from "lucide-react";
import type { ObservationDetails } from "../types";

interface ObservationDetailsCardProps {
  details: ObservationDetails;
  action?: string;
}

export function ObservationDetailsCard({ details, action }: ObservationDetailsCardProps) {
  if (!details) return null;

  const renderContent = () => {
    switch (details.type) {
      case "parse_hypothesis":
        return details.hypothesis && <HypothesisDetails hypothesis={details.hypothesis} />;

      case "decompose_questions":
        return details.questions && <QuestionsDetails questions={details.questions} count={details.count} />;

      case "search_rag":
      case "search_epmc":
      case "search_web":
        return details.papers && <SearchDetails papers={details.papers} totalCount={details.total_count} coverage={details.coverage} />;

      case "design_experiment":
        return details.experiment && <ExperimentDetails experiment={details.experiment} />;

      case "design_controls":
        return details.controls && <ControlsDetails controls={details.controls} count={details.count} />;

      case "suggest_measurements":
        return details.measurements && <MeasurementsDetails measurements={details.measurements} count={details.count} />;

      case "critique_design":
        return details.critique && <CritiqueDetails critique={details.critique} />;

      case "synthesize_plan":
        return details.plan && <PlanDetails plan={details.plan} isPlanB={false} />;

      case "generate_plan_b":
        return details.plan_b && <PlanBDetails planB={details.plan_b} />;

      default:
        return null;
    }
  };

  const content = renderContent();
  if (!content) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      className="mt-3 rounded-lg bg-[var(--oaria-surface)] border border-[var(--oaria-border)] overflow-hidden"
    >
      {content}
    </motion.div>
  );
}

// ─────────────────────────────────────────────────────────────
// Detail Components
// ─────────────────────────────────────────────────────────────

function HypothesisDetails({ hypothesis }: { hypothesis: NonNullable<ObservationDetails["hypothesis"]> }) {
  return (
    <div className="p-3 space-y-2">
      <div className="flex items-center gap-2 text-xs font-medium text-[var(--oaria-teal)]">
        <Microscope size={14} />
        가설 구조 분석 결과
      </div>
      <div className="grid gap-2 text-sm">
        <div className="flex gap-2">
          <span className="text-[var(--oaria-text-secondary)] min-w-[60px]">독립변수</span>
          <span className="font-medium">{hypothesis.iv || "-"}</span>
        </div>
        <div className="flex gap-2">
          <span className="text-[var(--oaria-text-secondary)] min-w-[60px]">종속변수</span>
          <span className="font-medium">{hypothesis.dv || "-"}</span>
        </div>
        {hypothesis.mechanism && (
          <div className="flex gap-2">
            <span className="text-[var(--oaria-text-secondary)] min-w-[60px]">메커니즘</span>
            <span>{hypothesis.mechanism}</span>
          </div>
        )}
        {hypothesis.mediators?.length > 0 && (
          <div className="flex gap-2">
            <span className="text-[var(--oaria-text-secondary)] min-w-[60px]">매개변수</span>
            <span>{hypothesis.mediators.join(", ")}</span>
          </div>
        )}
        <div className="flex items-center gap-2 pt-1">
          <div className="flex-1 h-1.5 bg-[var(--oaria-border)] rounded-full overflow-hidden">
            <div
              className="h-full bg-[var(--oaria-teal)] rounded-full"
              style={{ width: `${(hypothesis.confidence || 0) * 100}%` }}
            />
          </div>
          <span className="text-xs text-[var(--oaria-text-secondary)]">
            신뢰도 {((hypothesis.confidence || 0) * 100).toFixed(0)}%
          </span>
        </div>
      </div>
    </div>
  );
}

function QuestionsDetails({ questions, count }: { questions: NonNullable<ObservationDetails["questions"]>; count?: number }) {
  const categoryColors: Record<string, string> = {
    necessity: "bg-blue-500/10 text-blue-600",
    sufficiency: "bg-green-500/10 text-green-600",
    plausibility: "bg-purple-500/10 text-purple-600",
    ethicality: "bg-orange-500/10 text-orange-600",
  };

  return (
    <div className="p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs font-medium text-[var(--oaria-teal)]">
          <HelpCircle size={14} />
          검증 질문 {count || questions.length}개
        </div>
      </div>
      <ul className="space-y-2">
        {questions.map((q, i) => (
          <li key={q.id || i} className="text-sm">
            <div className="flex items-start gap-2">
              <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${categoryColors[q.category] || "bg-gray-500/10 text-gray-600"}`}>
                {q.category}
              </span>
              <span className="flex-1">{q.question}</span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function SearchDetails({ papers, totalCount, coverage }: { papers: NonNullable<ObservationDetails["papers"]>; totalCount?: number; coverage?: number }) {
  return (
    <div className="p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs font-medium text-[var(--oaria-teal)]">
          <BookOpen size={14} />
          검색 결과 {totalCount || papers.length}편
        </div>
        {coverage !== undefined && (
          <span className="text-xs text-[var(--oaria-text-secondary)]">
            관련도 {(coverage * 100).toFixed(0)}%
          </span>
        )}
      </div>
      <ul className="space-y-1.5">
        {papers.slice(0, 5).map((p, i) => (
          <li key={i} className="text-sm border-l-2 border-[var(--oaria-border)] pl-2">
            <div className="font-medium line-clamp-1">{p.title}</div>
            <div className="text-xs text-[var(--oaria-text-secondary)]">
              {p.authors?.slice(0, 2).join(", ")}{p.authors?.length > 2 ? " 외" : ""} · {p.year || ""} · {p.journal}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ExperimentDetails({ experiment }: { experiment: NonNullable<ObservationDetails["experiment"]> }) {
  return (
    <div className="p-3 space-y-2">
      <div className="flex items-center gap-2 text-xs font-medium text-[var(--oaria-teal)]">
        <FlaskConical size={14} />
        실험 설계
      </div>
      <div className="space-y-1.5 text-sm">
        <div className="font-medium">{experiment.name || "Untitled Experiment"}</div>
        <div className="flex gap-2 text-[var(--oaria-text-secondary)]">
          <span className="px-1.5 py-0.5 bg-[var(--oaria-border)] rounded text-xs">{experiment.type}</span>
          {experiment.duration && <span>{experiment.duration}</span>}
          {experiment.sample_size && <span>n={experiment.sample_size}</span>}
        </div>
        {experiment.objective && (
          <p className="text-[var(--oaria-text-secondary)]">{experiment.objective}</p>
        )}
        {experiment.methods?.length > 0 && (
          <div className="flex flex-wrap gap-1 pt-1">
            {experiment.methods.map((m, i) => (
              <span key={i} className="px-1.5 py-0.5 bg-blue-500/10 text-blue-600 rounded text-xs">
                {m}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ControlsDetails({ controls, count }: { controls: NonNullable<ObservationDetails["controls"]>; count?: number }) {
  return (
    <div className="p-3 space-y-2">
      <div className="flex items-center gap-2 text-xs font-medium text-[var(--oaria-teal)]">
        <CheckCircle2 size={14} />
        대조군 설계 {count || controls.length}개
      </div>
      <ul className="space-y-1.5">
        {controls.map((c, i) => (
          <li key={i} className="text-sm flex items-start gap-2">
            <span className="px-1.5 py-0.5 bg-green-500/10 text-green-600 rounded text-xs min-w-fit">
              {c.type}
            </span>
            <div>
              <span className="font-medium">{c.name}</span>
              {c.purpose && <span className="text-[var(--oaria-text-secondary)]"> - {c.purpose}</span>}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function MeasurementsDetails({ measurements, count }: { measurements: NonNullable<ObservationDetails["measurements"]>; count?: number }) {
  return (
    <div className="p-3 space-y-2">
      <div className="flex items-center gap-2 text-xs font-medium text-[var(--oaria-teal)]">
        <Gauge size={14} />
        측정 항목 {count || measurements.length}개
      </div>
      <ul className="space-y-1.5">
        {measurements.map((m, i) => (
          <li key={i} className="text-sm flex items-start gap-2">
            <span className={`px-1.5 py-0.5 rounded text-xs ${m.type === "primary" ? "bg-orange-500/10 text-orange-600" : "bg-gray-500/10 text-gray-600"}`}>
              {m.type}
            </span>
            <div>
              <span className="font-medium">{m.name}</span>
              {m.method && <span className="text-[var(--oaria-text-secondary)]"> ({m.method})</span>}
              {m.unit && <span className="text-[var(--oaria-text-secondary)]"> [{m.unit}]</span>}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function CritiqueDetails({ critique }: { critique: NonNullable<ObservationDetails["critique"]> }) {
  const scoreColor = critique.score >= 0.8 ? "text-green-600" : critique.score >= 0.6 ? "text-yellow-600" : "text-red-600";

  return (
    <div className="p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs font-medium text-[var(--oaria-teal)]">
          <FileText size={14} />
          설계 품질 평가
        </div>
        <span className={`text-sm font-bold ${scoreColor}`}>
          {(critique.score * 100).toFixed(0)}점
        </span>
      </div>
      {critique.strengths?.length > 0 && (
        <div>
          <div className="text-xs text-green-600 font-medium mb-1">강점</div>
          <ul className="space-y-0.5">
            {critique.strengths.map((s, i) => (
              <li key={i} className="text-sm flex items-start gap-1">
                <CheckCircle2 size={12} className="text-green-500 mt-0.5 shrink-0" />
                <span>{typeof s === "string" ? s : (s as { description?: string }).description || JSON.stringify(s)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {critique.issues?.length > 0 && (
        <div>
          <div className="text-xs text-red-600 font-medium mb-1">개선 필요</div>
          <ul className="space-y-0.5">
            {critique.issues.map((issue, i) => {
              // issue can be string or object with {type, severity, description, affected_experiment}
              const text = typeof issue === "string" ? issue : (issue as { description?: string }).description || JSON.stringify(issue);
              return (
                <li key={i} className="text-sm flex items-start gap-1">
                  <AlertCircle size={12} className="text-red-500 mt-0.5 shrink-0" />
                  <span>{text}</span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}

function PlanDetails({ plan }: { plan: NonNullable<ObservationDetails["plan"]>; isPlanB: boolean }) {
  return (
    <div className="p-3 space-y-2">
      <div className="flex items-center gap-2 text-xs font-medium text-[var(--oaria-teal)]">
        <FileText size={14} />
        실험 계획서 (Plan A) 생성 완료
      </div>
      <div className="text-sm text-[var(--oaria-text-secondary)]">
        {plan.experiment_count > 0 && `${plan.experiment_count}개 실험 포함`}
      </div>
    </div>
  );
}

function PlanBDetails({ planB }: { planB: NonNullable<ObservationDetails["plan_b"]> }) {
  return (
    <div className="p-3 space-y-2">
      <div className="flex items-center gap-2 text-xs font-medium text-[var(--oaria-teal)]">
        <FileText size={14} />
        대안 계획 (Plan B) 생성 완료
      </div>
      <div className="text-sm text-[var(--oaria-text-secondary)]">
        {planB.approach && <span>접근법: {planB.approach}</span>}
        {planB.cost_reduction && <span> · 비용 절감: {planB.cost_reduction}</span>}
      </div>
    </div>
  );
}

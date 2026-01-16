"use client";

import { useState, useEffect } from "react";
import { papersApi, type SimilarPaper, type SimilarPapersResponse } from "@/lib/api";

type SourceType = "hybrid" | "citation" | "reference" | "vector";

interface SimilarPapersProps {
  paperId: string; // UUID
  className?: string;
}

// 추천 유형별 스타일
const sourceStyles: Record<
  string,
  { bg: string; text: string; label: string; description: string }
> = {
  hybrid: {
    bg: "bg-purple-100 dark:bg-purple-900/30",
    text: "text-purple-700 dark:text-purple-300",
    label: "Hybrid",
    description: "여러 소스 조합 (가장 관련성 높음)",
  },
  citation: {
    bg: "bg-blue-100 dark:bg-blue-900/30",
    text: "text-blue-700 dark:text-blue-300",
    label: "Citation",
    description: "이 논문을 인용한 논문 (후속 연구)",
  },
  reference: {
    bg: "bg-green-100 dark:bg-green-900/30",
    text: "text-green-700 dark:text-green-300",
    label: "Reference",
    description: "이 논문이 인용한 논문 (기반 연구)",
  },
  vector: {
    bg: "bg-amber-100 dark:bg-amber-900/30",
    text: "text-amber-700 dark:text-amber-300",
    label: "Vector",
    description: "내용 유사도 기반",
  },
};

function buildEuropePMCLink(paper: SimilarPaper): string | null {
  if (paper.pmcid) {
    const pmcNum = paper.pmcid.replace(/^PMC/i, "");
    return `https://europepmc.org/article/PMC/${pmcNum}`;
  }
  if (paper.pmid) {
    return `https://europepmc.org/article/MED/${paper.pmid}`;
  }
  if (paper.doi) {
    return `https://doi.org/${paper.doi}`;
  }
  return null;
}

function SimilarPaperCard({ paper }: { paper: SimilarPaper }) {
  const style = sourceStyles[paper.recommendation_type] || sourceStyles.hybrid;
  const link = buildEuropePMCLink(paper);

  // Display ID
  const displayId = paper.pmcid || (paper.pmid ? `PMID:${paper.pmid}` : paper.doi ? `DOI:${paper.doi}` : "");

  return (
    <div className="p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 transition-colors">
      {/* Header */}
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <span
          className={`px-2 py-0.5 text-xs font-semibold rounded ${style.bg} ${style.text}`}
        >
          {style.label}
        </span>
        {displayId && (
          <span className="text-xs text-gray-500 dark:text-gray-400 font-mono">
            {displayId}
          </span>
        )}
        {paper.score > 0 && (
          <span className="ml-auto text-xs text-gray-400">
            Score: {paper.score.toFixed(2)}
          </span>
        )}
      </div>

      {/* Title */}
      <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-2 line-clamp-2">
        {paper.title || "(제목 없음)"}
      </h4>

      {/* Meta */}
      <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
        <div className="flex items-center gap-2">
          {paper.journal && <span>{paper.journal}</span>}
          {paper.year && <span>({paper.year})</span>}
        </div>
        {link && (
          <a
            href={link}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[var(--oaria-teal)] hover:underline flex items-center gap-1"
          >
            Europe PMC
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </a>
        )}
      </div>

      {/* Sources (for hybrid) */}
      {paper.sources && paper.sources.length > 1 && (
        <div className="mt-2 flex items-center gap-1">
          <span className="text-xs text-gray-400">Sources:</span>
          {paper.sources.map((src) => {
            const srcStyle = sourceStyles[src] || sourceStyles.hybrid;
            return (
              <span
                key={src}
                className={`px-1.5 py-0.5 text-[10px] rounded ${srcStyle.bg} ${srcStyle.text}`}
              >
                {srcStyle.label}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function SimilarPapers({ paperId, className = "" }: SimilarPapersProps) {
  const [activeSource, setActiveSource] = useState<SourceType>("hybrid");
  const [data, setData] = useState<SimilarPapersResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchSimilar() {
      setIsLoading(true);
      setError(null);

      try {
        const result = await papersApi.getSimilar(paperId, activeSource);
        setData(result);
      } catch (err) {
        console.error("Failed to fetch similar papers:", err);
        setError("유사 논문을 불러오는데 실패했습니다.");
      } finally {
        setIsLoading(false);
      }
    }

    fetchSimilar();
  }, [paperId, activeSource]);

  const tabs: { key: SourceType; label: string; count?: number }[] = [
    { key: "hybrid", label: "Hybrid" },
    { key: "citation", label: "Citations" },
    { key: "reference", label: "References" },
    { key: "vector", label: "Vector" },
  ];

  return (
    <div className={`${className}`}>
      {/* Legend */}
      <div className="mb-4 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg text-xs space-y-1">
        {Object.entries(sourceStyles).map(([key, style]) => (
          <div key={key} className="flex items-center gap-2">
            <span className={`w-3 h-3 rounded ${style.bg}`} />
            <span className="font-medium">{style.label}:</span>
            <span className="text-gray-500 dark:text-gray-400">{style.description}</span>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-4 flex-wrap">
        {tabs.map((tab) => {
          const style = sourceStyles[tab.key];
          const isActive = activeSource === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveSource(tab.key)}
              className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-all ${
                isActive
                  ? `${style.bg} ${style.text} ring-2 ring-current ring-offset-1`
                  : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700"
              }`}
            >
              {tab.label}
              {data && activeSource === tab.key && (
                <span className="ml-1.5 px-1.5 py-0.5 text-xs rounded-full bg-black/10 dark:bg-white/10">
                  {data.total}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div className="space-y-3">
        {isLoading ? (
          <div className="flex justify-center py-8">
            <div className="w-8 h-8 border-2 border-[var(--oaria-teal)] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : error ? (
          <div className="text-center py-8 text-gray-500">{error}</div>
        ) : data && data.items.length > 0 ? (
          data.items.map((paper, idx) => (
            <SimilarPaperCard key={`${paper.pmcid || paper.pmid || idx}`} paper={paper} />
          ))
        ) : (
          <div className="text-center py-8 text-gray-500 dark:text-gray-400">
            유사 논문이 없습니다.
          </div>
        )}
      </div>
    </div>
  );
}

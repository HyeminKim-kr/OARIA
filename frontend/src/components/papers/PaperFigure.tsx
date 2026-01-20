"use client";

import { useState } from "react";
import type { Figure } from "@/lib/api";

interface PaperFigureProps {
  pmcid: string;
  figure: Figure;
  className?: string;
}

/**
 * Figure 이미지 URL 생성 (Hotlink 방식)
 *
 * Europe PMC 서버에서 직접 이미지를 로드합니다.
 * Primary URL 실패 시 fallback URL들을 순차적으로 시도합니다.
 */
function buildFigureUrls(pmcid: string, graphicHref: string): string[] {
  // PMCID에서 숫자만 추출 (PMC12345678 → 12345678)
  const pmcNumber = pmcid.replace(/^PMC/i, "");

  return [
    // Primary: Europe PMC - JPG
    `https://europepmc.org/articles/PMC${pmcNumber}/bin/${graphicHref}.jpg`,
    // Fallback 1: Europe PMC - PNG
    `https://europepmc.org/articles/PMC${pmcNumber}/bin/${graphicHref}.png`,
    // Fallback 2: NCBI PubMed Central - JPG
    `https://www.ncbi.nlm.nih.gov/pmc/articles/PMC${pmcNumber}/bin/${graphicHref}.jpg`,
    // Fallback 3: NCBI PubMed Central - PNG
    `https://www.ncbi.nlm.nih.gov/pmc/articles/PMC${pmcNumber}/bin/${graphicHref}.png`,
  ];
}

export function PaperFigure({ pmcid, figure, className = "" }: PaperFigureProps) {
  const urls = buildFigureUrls(pmcid, figure.graphic_href);
  const [currentUrlIndex, setCurrentUrlIndex] = useState(0);
  const [hasError, setHasError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const handleError = () => {
    // 다음 fallback URL 시도
    if (currentUrlIndex < urls.length - 1) {
      setCurrentUrlIndex((prev) => prev + 1);
    } else {
      // 모든 URL 실패
      setHasError(true);
      setIsLoading(false);
    }
  };

  const handleLoad = () => {
    setIsLoading(false);
  };

  if (hasError) {
    return (
      <div className={`bg-gray-100 dark:bg-gray-800 rounded-lg p-4 ${className}`}>
        <div className="flex flex-col items-center justify-center py-8 text-gray-500">
          <svg
            className="w-12 h-12 mb-2"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
            />
          </svg>
          <span className="text-sm">{figure.label} - 이미지를 불러올 수 없습니다</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`bg-gray-50 dark:bg-gray-900 rounded-lg overflow-hidden ${className}`}>
      {/* Figure Label */}
      <div className="px-4 py-2 bg-gray-100 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <span className="font-semibold text-sm text-gray-700 dark:text-gray-300">
          {figure.label}
        </span>
      </div>

      {/* Image Container */}
      <div className="relative w-full min-h-[200px] flex items-center justify-center p-4">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-100 dark:bg-gray-800">
            <div className="w-8 h-8 border-2 border-[var(--oaria-teal)] border-t-transparent rounded-full animate-spin" />
          </div>
        )}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={urls[currentUrlIndex]}
          alt={figure.label}
          className={`max-w-full max-h-[500px] object-contain ${isLoading ? "opacity-0" : "opacity-100"}`}
          onError={handleError}
          onLoad={handleLoad}
        />
      </div>

      {/* Caption */}
      {figure.caption && (
        <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
            {figure.caption}
          </p>
        </div>
      )}
    </div>
  );
}

/**
 * Figure 갤러리 (여러 Figure를 표시)
 */
interface FigureGalleryProps {
  pmcid: string;
  figures: Figure[];
  className?: string;
}

export function FigureGallery({ pmcid, figures, className = "" }: FigureGalleryProps) {
  if (figures.length === 0) {
    return null;
  }

  return (
    <div className={`space-y-6 ${className}`}>
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
          />
        </svg>
        Figures ({figures.length})
      </h3>
      <div className="space-y-6">
        {figures.map((figure) => (
          <PaperFigure key={figure.id} pmcid={pmcid} figure={figure} />
        ))}
      </div>
    </div>
  );
}

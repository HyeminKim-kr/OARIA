'use client';

import { useState } from 'react';
import { ChevronDown, HelpCircle, Settings2, BookOpen, X, Copy, Check } from 'lucide-react';
import { StrategiesResponse, StrategiesDetailResponse, StrategyInfo } from '@/lib/api';

interface StrategySelectionPanelProps {
  strategies?: StrategiesResponse;
  strategiesDetail?: StrategiesDetailResponse;
  selectedStrategies: {
    chunker: string;
    embedder: string;
    retriever: string;
    reranker: string;
  };
  onStrategyChange: (key: string, value: string) => void;
}

// 전략 이름으로 상세 정보 찾기
function getStrategyDescription(
  strategiesDetail: StrategyInfo[] | undefined,
  name: string
): string {
  const info = strategiesDetail?.find((s) => s.name === name);
  return info?.description || '';
}

function StrategyDropdown({
  label,
  value,
  options,
  disabled,
  disabledReason,
  description,
  onShowDetail,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  disabled?: boolean;
  disabledReason?: string;
  description?: string;
  onShowDetail: () => void;
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex-1 min-w-[160px]">
      <div className="flex items-center justify-between mb-1">
        <label className="text-xs font-medium text-gray-600">{label}</label>
        <button
          onClick={onShowDetail}
          className="flex items-center gap-0.5 text-xs text-indigo-600 hover:text-indigo-800 hover:underline"
        >
          <HelpCircle className="h-3 w-3" />
          <span>설명</span>
        </button>
      </div>
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          className={`w-full appearance-none rounded-md border px-3 py-2 pr-8 text-sm focus:outline-none focus:ring-1 ${
            disabled
              ? 'border-gray-200 bg-gray-50 text-gray-400 cursor-not-allowed'
              : 'border-gray-300 bg-white text-gray-700 focus:border-blue-500 focus:ring-blue-500'
          }`}
        >
          {options.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
        <ChevronDown className={`pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 ${disabled ? 'text-gray-300' : 'text-gray-400'}`} />
      </div>
      {disabled && disabledReason && (
        <p className="mt-1 text-xs text-gray-400">{disabledReason}</p>
      )}
    </div>
  );
}

// 전략 상세 설명 모달
function StrategyDetailModal({
  title,
  strategyName,
  description,
  isDisabled,
  disabledReason,
  onClose,
}: {
  title: string;
  strategyName: string;
  description: string;
  isDisabled?: boolean;
  disabledReason?: string;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-lg bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b px-4 py-3">
          <div>
            <h3 className="font-semibold text-gray-900">{title}</h3>
            <p className="text-sm text-indigo-600">{strategyName}</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-1 hover:bg-gray-100">
            <X className="h-5 w-5 text-gray-500" />
          </button>
        </div>
        <div className="p-4">
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-gray-700">
            {description || '설명이 없습니다.'}
          </p>
          {isDisabled && disabledReason && (
            <div className="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
              <strong>⚠️ 참고:</strong> {disabledReason}
            </div>
          )}
        </div>
        <div className="border-t px-4 py-3">
          <button
            onClick={onClose}
            className="w-full rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800"
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}

function StrategyGuideModal({ onClose }: { onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  const readmePath = 'backend/app/rag/README.md';

  const handleCopy = () => {
    navigator.clipboard.writeText(readmePath);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="max-h-[80vh] w-full max-w-2xl overflow-y-auto rounded-lg bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 flex items-center justify-between border-b bg-white px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-900">새 RAG 전략 추가 가이드</h2>
          <button onClick={onClose} className="rounded-lg p-1 hover:bg-gray-100">
            <X className="h-5 w-5 text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <div className="space-y-6 p-6">
          {/* README 위치 안내 */}
          <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
            <h3 className="flex items-center gap-2 font-medium text-blue-900">
              <BookOpen className="h-5 w-5" />
              상세 가이드 문서 위치
            </h3>
            <p className="mt-2 text-sm text-blue-700">
              새 전략을 추가하려면 아래 README 파일을 Claude Code에게 알려주세요:
            </p>
            <div className="mt-3 flex items-center gap-2">
              <code className="flex-1 rounded bg-blue-100 px-3 py-2 text-sm font-mono text-blue-800">
                {readmePath}
              </code>
              <button
                onClick={handleCopy}
                className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              </button>
            </div>
          </div>

          {/* Claude Code 사용 예시 */}
          <div>
            <h3 className="font-medium text-gray-900">Claude Code 프롬프트 예시</h3>
            <div className="mt-2 space-y-2 rounded-lg bg-gray-50 p-4 text-sm">
              <p className="text-gray-600">새 Reranker를 추가하고 싶을 때:</p>
              <code className="block rounded bg-gray-200 p-3 text-gray-800">
                &quot;backend/app/rag/README.md 읽고 Cohere Reranker 추가해줘&quot;
              </code>
              <p className="mt-3 text-gray-600">새 Embedder를 추가하고 싶을 때:</p>
              <code className="block rounded bg-gray-200 p-3 text-gray-800">
                &quot;backend/app/rag/README.md 보고 Voyage AI embedder 추가해줘&quot;
              </code>
            </div>
          </div>

          {/* 간략한 구조 설명 */}
          <div>
            <h3 className="font-medium text-gray-900">디렉토리 구조</h3>
            <pre className="mt-2 overflow-x-auto rounded-lg bg-gray-900 p-4 text-sm text-gray-100">
{`backend/app/rag/
├── README.md          # 📖 가이드 문서
├── registry.py        # 전략 레지스트리
├── chunkers/          # 청킹 전략
├── embedders/         # 임베딩 모델
├── retrievers/        # 검색 전략
└── rerankers/         # 리랭킹 모델`}
            </pre>
          </div>

          {/* 체크리스트 */}
          <div>
            <h3 className="font-medium text-gray-900">새 전략 추가 체크리스트</h3>
            <ul className="mt-2 space-y-2 text-sm text-gray-600">
              <li className="flex items-start gap-2">
                <span className="mt-0.5 h-4 w-4 rounded border border-gray-300" />
                해당 디렉토리의 <code className="rounded bg-gray-100 px-1">base.py</code>에서 Protocol 확인
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-0.5 h-4 w-4 rounded border border-gray-300" />
                <code className="rounded bg-gray-100 px-1">@register_*</code> 데코레이터로 구현체 작성
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-0.5 h-4 w-4 rounded border border-gray-300" />
                <code className="rounded bg-gray-100 px-1">__init__.py</code>에서 import 추가
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-0.5 h-4 w-4 rounded border border-gray-300" />
                단위 테스트 작성
              </li>
            </ul>
          </div>
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 border-t bg-gray-50 px-6 py-4">
          <button
            onClick={onClose}
            className="w-full rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800"
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}

// 선택된 값이 옵션에 없으면 추가 (DB 설정과 API 응답이 다를 수 있음)
function ensureValueInOptions(options: string[], value: string): string[] {
  if (value && !options.includes(value)) {
    return [value, ...options];
  }
  return options;
}

type StrategyType = 'chunker' | 'embedder' | 'retriever' | 'reranker' | null;

export function StrategySelectionPanel({
  strategies,
  strategiesDetail,
  selectedStrategies,
  onStrategyChange,
}: StrategySelectionPanelProps) {
  const [showGuide, setShowGuide] = useState(false);
  const [showDetailFor, setShowDetailFor] = useState<StrategyType>(null);

  // 기본 옵션 설정 + 현재 선택된 값이 없으면 추가
  const chunkerOptions = ensureValueInOptions(
    strategies?.chunkers ?? ['semantic'],
    selectedStrategies.chunker
  );
  const embedderOptions = ensureValueInOptions(
    strategies?.embedders ?? ['openai'],
    selectedStrategies.embedder
  );
  const retrieverOptions = ensureValueInOptions(
    strategies?.retrievers ?? ['hybrid'],
    selectedStrategies.retriever
  );
  const rerankerOptions = ensureValueInOptions(
    ['none', ...(strategies?.rerankers?.filter(r => r !== 'none') ?? ['bge'])],
    selectedStrategies.reranker
  );

  // 선택된 전략의 설명 가져오기
  const chunkerDesc = getStrategyDescription(strategiesDetail?.chunkers, selectedStrategies.chunker);
  const embedderDesc = getStrategyDescription(strategiesDetail?.embedders, selectedStrategies.embedder);
  const retrieverDesc = getStrategyDescription(strategiesDetail?.retrievers, selectedStrategies.retriever);
  const rerankerDesc = selectedStrategies.reranker === 'none'
    ? '리랭킹을 사용하지 않습니다.\n\nA/B 테스트에서 리랭킹 효과를 비교할 때 baseline으로 사용합니다.'
    : getStrategyDescription(strategiesDetail?.rerankers, selectedStrategies.reranker);

  // 모달에 표시할 정보
  const detailModalInfo: Record<Exclude<StrategyType, null>, { title: string; name: string; desc: string; disabled?: boolean; disabledReason?: string }> = {
    chunker: {
      title: 'Chunker (청킹 전략)',
      name: selectedStrategies.chunker,
      desc: chunkerDesc,
      disabled: true,
      disabledReason: '인덱싱 시점에 결정되어 검색 시 변경할 수 없습니다.',
    },
    embedder: {
      title: 'Embedder (임베딩 모델)',
      name: selectedStrategies.embedder,
      desc: embedderDesc,
      disabled: true,
      disabledReason: '인덱싱 시점에 결정되어 검색 시 변경할 수 없습니다.',
    },
    retriever: {
      title: 'Retriever (검색 전략)',
      name: selectedStrategies.retriever,
      desc: retrieverDesc,
    },
    reranker: {
      title: 'Reranker (재정렬 모델)',
      name: selectedStrategies.reranker,
      desc: rerankerDesc,
    },
  };

  return (
    <>
      <div className="rounded-lg border border-indigo-200 bg-gradient-to-r from-indigo-50 to-purple-50 p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Settings2 className="h-4 w-4 text-indigo-600" />
            <h3 className="text-sm font-semibold text-indigo-900">RAG 전략 선택</h3>
            <span className="text-xs text-indigo-500">(검색 시점에 변경 가능한 항목만 활성화)</span>
          </div>
          <button
            onClick={() => setShowGuide(true)}
            className="flex items-center gap-1 rounded-lg bg-indigo-100 px-2.5 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-200 transition-colors"
          >
            <BookOpen className="h-3.5 w-3.5" />
            새 전략 추가 가이드
          </button>
        </div>

        <div className="flex flex-wrap gap-4">
          <StrategyDropdown
            label="Chunker"
            value={selectedStrategies.chunker}
            options={chunkerOptions}
            disabled
            disabledReason="인덱싱 시점에 결정됨"
            description={chunkerDesc}
            onShowDetail={() => setShowDetailFor('chunker')}
            onChange={(v) => onStrategyChange('chunker', v)}
          />

          <StrategyDropdown
            label="Embedder"
            value={selectedStrategies.embedder}
            options={embedderOptions}
            disabled
            disabledReason="인덱싱 시점에 결정됨"
            description={embedderDesc}
            onShowDetail={() => setShowDetailFor('embedder')}
            onChange={(v) => onStrategyChange('embedder', v)}
          />

          <StrategyDropdown
            label="Retriever"
            value={selectedStrategies.retriever}
            options={retrieverOptions}
            description={retrieverDesc}
            onShowDetail={() => setShowDetailFor('retriever')}
            onChange={(v) => onStrategyChange('retriever', v)}
          />

          <StrategyDropdown
            label="Reranker"
            value={selectedStrategies.reranker}
            options={rerankerOptions}
            description={rerankerDesc}
            onShowDetail={() => setShowDetailFor('reranker')}
            onChange={(v) => onStrategyChange('reranker', v)}
          />
        </div>
      </div>

      {showGuide && <StrategyGuideModal onClose={() => setShowGuide(false)} />}

      {showDetailFor && (
        <StrategyDetailModal
          title={detailModalInfo[showDetailFor].title}
          strategyName={detailModalInfo[showDetailFor].name}
          description={detailModalInfo[showDetailFor].desc}
          isDisabled={detailModalInfo[showDetailFor].disabled}
          disabledReason={detailModalInfo[showDetailFor].disabledReason}
          onClose={() => setShowDetailFor(null)}
        />
      )}
    </>
  );
}

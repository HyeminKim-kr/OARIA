type EmbeddingStatusFilter = 'all' | 'not_started' | 'pending' | 'processing' | 'completed' | 'failed';

interface EmbeddingFilterTabsProps {
  value: EmbeddingStatusFilter;
  onChange: (value: EmbeddingStatusFilter) => void;
}

const OPTIONS = [
  { value: 'all', label: '전체' },
  { value: 'not_started', label: '미시작' },
  { value: 'pending', label: '대기' },
  { value: 'processing', label: '처리중' },
  { value: 'completed', label: '완료' },
  { value: 'failed', label: '실패' },
] as const;

export function EmbeddingFilterTabs({ value, onChange }: EmbeddingFilterTabsProps) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-gray-500">임베딩 상태:</span>
      <div className="flex gap-1">
        {OPTIONS.map((option) => (
          <button
            key={option.value}
            onClick={() => onChange(option.value)}
            className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
              value === option.value
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

import {
  FlaskConical,
  BarChart3,
  History,
  BookOpen,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface LabHeaderProps {
  status?: { available: boolean; latencyMs?: number };
  showStats: boolean;
  showHistory: boolean;
  showHelp: boolean;
  onToggleStats: () => void;
  onToggleHistory: () => void;
  onToggleHelp: () => void;
}

export function LabHeader({
  status,
  showStats,
  showHistory,
  showHelp,
  onToggleStats,
  onToggleHistory,
  onToggleHelp,
}: LabHeaderProps) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900">
          <FlaskConical className="h-6 w-6" />
          RAG Lab
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          RAG 검색 및 답변 품질을 테스트합니다
        </p>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={onToggleStats}
          className={cn(
            'flex items-center gap-1 rounded-full px-3 py-1 text-sm transition-colors',
            showStats
              ? 'bg-emerald-100 text-emerald-700'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          )}
        >
          <BarChart3 className="h-4 w-4" />
          통계
        </button>
        <button
          onClick={onToggleHistory}
          className={cn(
            'flex items-center gap-1 rounded-full px-3 py-1 text-sm transition-colors',
            showHistory
              ? 'bg-purple-100 text-purple-700'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          )}
        >
          <History className="h-4 w-4" />
          히스토리
        </button>
        <button
          onClick={onToggleHelp}
          className={cn(
            'flex items-center gap-1 rounded-full px-3 py-1 text-sm transition-colors',
            showHelp
              ? 'bg-blue-100 text-blue-700'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          )}
        >
          <BookOpen className="h-4 w-4" />
          도움말
        </button>
        {status?.available ? (
          <span className="flex items-center gap-1 rounded-full bg-green-100 px-3 py-1 text-sm text-green-700">
            <CheckCircle2 className="h-4 w-4" />
            Backend 연결됨
            {status.latencyMs && (
              <span className="text-green-600">({status.latencyMs}ms)</span>
            )}
          </span>
        ) : (
          <span className="flex items-center gap-1 rounded-full bg-red-100 px-3 py-1 text-sm text-red-700">
            <XCircle className="h-4 w-4" />
            Backend 연결 실패
          </span>
        )}
      </div>
    </div>
  );
}

import Link from 'next/link';
import { AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ErrorInfo } from '../_lib';

interface LabErrorStateProps {
  errorInfo: ErrorInfo;
}

export function LabErrorState({ errorInfo }: LabErrorStateProps) {
  return (
    <div
      className={cn(
        'rounded-lg border p-6',
        errorInfo.type === 'no_data'
          ? 'border-yellow-200 bg-yellow-50'
          : 'border-red-200 bg-red-50'
      )}
    >
      <div className="flex items-start gap-3">
        <AlertTriangle
          className={cn(
            'h-6 w-6 flex-shrink-0',
            errorInfo.type === 'no_data' ? 'text-yellow-600' : 'text-red-600'
          )}
        />
        <div>
          <h3
            className={cn(
              'font-medium',
              errorInfo.type === 'no_data' ? 'text-yellow-800' : 'text-red-800'
            )}
          >
            {errorInfo.type === 'no_data' ? '데이터 준비 필요' : '오류 발생'}
          </h3>
          <p
            className={cn(
              'mt-1 text-sm',
              errorInfo.type === 'no_data' ? 'text-yellow-700' : 'text-red-700'
            )}
          >
            {errorInfo.message}
          </p>
          {errorInfo.type === 'no_data' && (
            <Link
              href="/papers"
              className="mt-3 inline-flex items-center gap-1 rounded-md bg-yellow-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-yellow-700"
            >
              Papers 페이지로 이동
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}

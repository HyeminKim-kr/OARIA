import { FlaskConical } from 'lucide-react';

export function LabEmptyState() {
  return (
    <div className="rounded-lg bg-gray-50 py-12 text-center">
      <FlaskConical className="mx-auto h-12 w-12 text-gray-400" />
      <h3 className="mt-4 text-lg font-medium text-gray-900">테스트 준비 완료</h3>
      <p className="mt-2 text-sm text-gray-500">위에서 질문을 입력하고 테스트를 실행하세요</p>
    </div>
  );
}

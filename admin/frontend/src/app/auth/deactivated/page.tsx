'use client';

import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { UserX } from 'lucide-react';

function DeactivatedContent() {
  const searchParams = useSearchParams();
  const email = searchParams.get('email');

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8 p-8">
        <div className="text-center">
          <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-gray-200">
            <UserX className="h-8 w-8 text-gray-600" />
          </div>
          <h1 className="mt-4 text-2xl font-bold text-gray-900">
            계정이 비활성화되었습니다
          </h1>
          <p className="mt-2 text-gray-600">
            관리자가 귀하의 계정을 비활성화했습니다.
          </p>
        </div>

        <div className="bg-white py-8 px-4 shadow rounded-lg sm:px-10">
          <div className="text-center space-y-4">
            {email && (
              <p className="text-sm text-gray-700">
                로그인 이메일: <strong>{email}</strong>
              </p>
            )}
            <p className="text-sm text-gray-500">
              계정 재활성화가 필요하시다면 관리자에게 문의해주세요.
            </p>
          </div>
        </div>

        <div className="text-center">
          <Link
            href="/auth"
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            다른 계정으로 로그인
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function DeactivatedPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-600" />
        </div>
      }
    >
      <DeactivatedContent />
    </Suspense>
  );
}

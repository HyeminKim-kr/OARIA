'use client';

import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Clock } from 'lucide-react';

function PendingContent() {
  const searchParams = useSearchParams();
  const email = searchParams.get('email');

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8 p-8">
        <div className="text-center">
          <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-yellow-100">
            <Clock className="h-8 w-8 text-yellow-600" />
          </div>
          <h1 className="mt-4 text-2xl font-bold text-gray-900">
            승인 대기 중
          </h1>
          <p className="mt-2 text-gray-600">
            관리자 승인을 기다리고 있습니다.
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
              Super Admin이 귀하의 계정을 승인하면 로그인이 가능합니다.
              <br />
              승인까지 시간이 걸릴 수 있습니다.
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

export default function PendingPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-yellow-600" />
        </div>
      }
    >
      <PendingContent />
    </Suspense>
  );
}

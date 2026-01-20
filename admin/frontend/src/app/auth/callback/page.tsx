'use client';

import { useEffect, useRef, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';

function CallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { handleOAuthCallback } = useAuth();
  const processedRef = useRef(false);

  useEffect(() => {
    // 이미 처리했으면 스킵 (StrictMode 대응)
    if (processedRef.current) return;

    const accessToken = searchParams.get('access_token');
    const refreshToken = searchParams.get('refresh_token');

    if (accessToken && refreshToken) {
      processedRef.current = true;

      // AuthContext를 통해 토큰 저장 + 사용자 정보 가져오기
      handleOAuthCallback(accessToken, refreshToken).then((success) => {
        if (success) {
          router.replace('/');
        } else {
          router.replace('/auth');
        }
      });
    } else {
      // 토큰이 없으면 로그인 페이지로
      router.replace('/auth');
    }
  }, [searchParams, router, handleOAuthCallback]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto" />
        <p className="mt-4 text-gray-600">로그인 처리 중...</p>
      </div>
    </div>
  );
}

export default function CallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
        </div>
      }
    >
      <CallbackContent />
    </Suspense>
  );
}

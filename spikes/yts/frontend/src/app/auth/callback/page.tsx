"use client";

import { Suspense, useEffect, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";

function AuthCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setTokens } = useAuth();
  const processedRef = useRef(false);

  useEffect(() => {
    const handleCallback = async () => {
      // 중복 실행 방지
      if (processedRef.current) return;
      processedRef.current = true;

      const accessToken = searchParams.get("access_token");
      const refreshToken = searchParams.get("refresh_token");

      if (!accessToken || !refreshToken) {
        console.error("Missing tokens in callback");
        router.replace("/?error=missing_tokens");
        return;
      }

      try {
        await setTokens(accessToken, refreshToken);
        // 로그인 성공 시 메인 페이지로 이동
        router.replace("/main");
      } catch (error) {
        console.error("Auth callback error:", error);
        router.replace("/?error=auth_failed");
      }
    };

    handleCallback();
  }, [searchParams, setTokens, router]);

  return (
    <div className="text-center">
      <div className="w-12 h-12 border-4 border-[var(--oaria-teal)] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
      <p className="font-[family-name:var(--font-dm-sans)] text-[var(--oaria-text-secondary)]">
        로그인 처리 중...
      </p>
    </div>
  );
}

function LoadingFallback() {
  return (
    <div className="text-center">
      <div className="w-12 h-12 border-4 border-[var(--oaria-border)] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
      <p className="font-[family-name:var(--font-dm-sans)] text-[var(--oaria-tagline)]">
        Loading...
      </p>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
      <Suspense fallback={<LoadingFallback />}>
        <AuthCallbackContent />
      </Suspense>
    </div>
  );
}

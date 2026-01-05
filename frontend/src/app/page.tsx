"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";

export default function Home() {
  const router = useRouter();
  const { isAuthenticated, isLoading, user, login, logout } = useAuth();

  // 로그인 상태면 메인 페이지로 리다이렉트
  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace("/main");
    }
  }, [isAuthenticated, isLoading, router]);

  // 로딩 중이거나 리다이렉트 중일 때 로딩 화면 표시
  if (isLoading || isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
        <div className="w-12 h-12 border-4 border-[var(--oaria-teal)] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--background)]">
      {/* Header */}
      <header className="fixed top-0 left-0 right-0 z-50 bg-[var(--background)]/80 backdrop-blur-md border-b border-[var(--oaria-border)]">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          {/* Logo - Horizontal with Tagline (from oaria-logo-assets.html) */}
          <svg width="160" height="48" viewBox="0 0 240 72" fill="none" xmlns="http://www.w3.org/2000/svg">
            {/* Triple Gate Icon */}
            <g transform="translate(3, 5)">
              <circle cx="31" cy="31" r="28" stroke="var(--oaria-light-ring)" strokeWidth="2" fill="none"/>
              <circle cx="31" cy="31" r="28" stroke="var(--oaria-teal)" strokeWidth="2.5" strokeDasharray="44 132" strokeLinecap="round" fill="none"/>
              <circle cx="31" cy="31" r="21" stroke="var(--oaria-light-ring)" strokeWidth="2" fill="none"/>
              <circle cx="31" cy="31" r="21" stroke="var(--oaria-light-teal)" strokeWidth="2.5" strokeDasharray="33 99" strokeLinecap="round" fill="none" transform="rotate(60 31 31)"/>
              <circle cx="31" cy="31" r="14" stroke="var(--oaria-light-ring)" strokeWidth="2" fill="none"/>
              <circle cx="31" cy="31" r="14" stroke="var(--oaria-coral)" strokeWidth="2.5" strokeDasharray="22 66" strokeLinecap="round" fill="none" transform="rotate(120 31 31)"/>
              <circle cx="31" cy="31" r="6.5" fill="var(--oaria-navy)"/>
              <circle cx="31" cy="31" r="3.25" fill="white"/>
            </g>
            {/* Text */}
            <g transform="translate(75, 18)">
              <text x="0" y="28" fontFamily="var(--font-outfit), Outfit, sans-serif" fontSize="36" fontWeight="600" fill="var(--oaria-teal)" letterSpacing="0.12em">OARIA</text>
              <text x="3.25" y="44" fontFamily="var(--font-dm-sans), DM Sans, sans-serif" fontSize="8.6" fontWeight="500" fill="var(--oaria-tagline)" textLength="123.5" lengthAdjust="spacing">RESEARCH INTELLIGENCE</text>
            </g>
          </svg>

          {/* Nav */}
          <nav className="hidden md:flex items-center gap-8">
            <a href="#features" className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] hover:text-[var(--oaria-teal)] transition-colors">
              Features
            </a>
            <a href="#about" className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] hover:text-[var(--oaria-teal)] transition-colors">
              About
            </a>
            <a href="#contact" className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] hover:text-[var(--oaria-teal)] transition-colors">
              Contact
            </a>
          </nav>

          {/* Auth */}
          {isLoading ? (
            <div className="w-24 h-10 bg-[var(--oaria-border)] rounded-full animate-pulse" />
          ) : isAuthenticated ? (
            <div className="flex items-center gap-4">
              {user?.picture && (
                <img
                  src={user.picture}
                  alt={user.name || "User"}
                  className="w-8 h-8 rounded-full"
                />
              )}
              <button
                onClick={logout}
                className="border border-[var(--oaria-border)] hover:border-[var(--oaria-teal)] text-[var(--foreground)] font-[family-name:var(--font-dm-sans)] text-sm font-medium px-5 py-2.5 rounded-full transition-colors"
              >
                Logout
              </button>
            </div>
          ) : (
            <button
              onClick={login}
              className="bg-[var(--oaria-teal)] hover:bg-[var(--oaria-light-teal)] text-white font-[family-name:var(--font-dm-sans)] text-sm font-medium px-5 py-2.5 rounded-full transition-colors flex items-center gap-2"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
              </svg>
              Sign in with Google
            </button>
          )}
        </div>
      </header>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-4xl mx-auto text-center">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 bg-[var(--oaria-teal)]/10 text-[var(--oaria-teal)] font-[family-name:var(--font-dm-sans)] text-sm font-medium px-4 py-2 rounded-full mb-8">
            <span className="w-2 h-2 bg-[var(--oaria-coral)] rounded-full animate-pulse"></span>
            Research Intelligence Platform
          </div>

          {/* Heading */}
          <h1 className="font-[family-name:var(--font-outfit)] text-5xl md:text-6xl font-bold text-[var(--foreground)] leading-tight mb-6">
            AI-Powered
            <span className="text-[var(--oaria-teal)]"> Cancer Research </span>
            Assistant
          </h1>

          {/* Subheading */}
          <p className="font-[family-name:var(--font-dm-sans)] text-lg text-[var(--oaria-text-secondary)] max-w-2xl mx-auto mb-10">
            OARIA는 최신 암 연구 논문을 분석하고, 신뢰할 수 있는 정보를 제공하는
            AI 기반 연구 인텔리전스 플랫폼입니다.
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <button className="w-full sm:w-auto bg-[var(--oaria-teal)] hover:bg-[var(--oaria-light-teal)] text-white font-[family-name:var(--font-dm-sans)] font-medium px-8 py-4 rounded-full transition-colors flex items-center justify-center gap-2">
              Start Research
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M4 10H16M16 10L11 5M16 10L11 15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
            <button className="w-full sm:w-auto border border-[var(--oaria-border)] hover:border-[var(--oaria-teal)] text-[var(--foreground)] font-[family-name:var(--font-dm-sans)] font-medium px-8 py-4 rounded-full transition-colors">
              Learn More
            </button>
          </div>
        </div>

        {/* Hero Visual */}
        <div className="max-w-5xl mx-auto mt-16">
          <div className="relative bg-gradient-to-br from-[var(--oaria-teal)]/5 to-[var(--oaria-coral)]/5 rounded-3xl border border-[var(--oaria-border)] p-8 md:p-12">
            {/* Decorative circles */}
            <div className="absolute top-4 right-4 w-24 h-24 bg-[var(--oaria-teal)]/10 rounded-full blur-2xl"></div>
            <div className="absolute bottom-4 left-4 w-32 h-32 bg-[var(--oaria-coral)]/10 rounded-full blur-2xl"></div>

            {/* Chat Preview */}
            <div className="relative bg-[var(--background)] rounded-2xl shadow-lg border border-[var(--oaria-border)] overflow-hidden">
              {/* Chat Header */}
              <div className="flex items-center gap-3 px-6 py-4 border-b border-[var(--oaria-border)]">
                <div className="flex gap-2">
                  <div className="w-3 h-3 rounded-full bg-[var(--oaria-coral)]"></div>
                  <div className="w-3 h-3 rounded-full bg-yellow-400"></div>
                  <div className="w-3 h-3 rounded-full bg-green-400"></div>
                </div>
                <span className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-tagline)]">OARIA Research Assistant</span>
              </div>

              {/* Chat Content */}
              <div className="p-6 space-y-4">
                {/* User Message */}
                <div className="flex justify-end">
                  <div className="bg-[var(--oaria-teal)] text-white font-[family-name:var(--font-dm-sans)] text-sm px-4 py-3 rounded-2xl rounded-br-md max-w-md">
                    폐암 3기 환자에게 적용 가능한 최신 면역치료법에 대해 알려줘
                  </div>
                </div>

                {/* AI Response */}
                <div className="flex justify-start">
                  <div className="bg-[var(--oaria-border)]/50 font-[family-name:var(--font-dm-sans)] text-sm px-4 py-3 rounded-2xl rounded-bl-md max-w-lg">
                    <p className="mb-3">폐암 3기 환자에게 적용 가능한 주요 면역치료법을 정리해드리겠습니다:</p>
                    <ul className="space-y-2 text-[var(--oaria-text-secondary)]">
                      <li className="flex items-start gap-2">
                        <span className="text-[var(--oaria-teal)]">•</span>
                        <span><strong>PD-1/PD-L1 억제제</strong>: Pembrolizumab, Nivolumab</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="text-[var(--oaria-teal)]">•</span>
                        <span><strong>병용 요법</strong>: 화학요법 + 면역치료</span>
                      </li>
                    </ul>
                    <p className="mt-3 text-xs text-[var(--oaria-tagline)]">출처: PMID:38291234, PMID:38156789</p>
                  </div>
                </div>
              </div>

              {/* Chat Input */}
              <div className="px-6 py-4 border-t border-[var(--oaria-border)]">
                <div className="flex items-center gap-3 bg-[var(--oaria-border)]/30 rounded-full px-4 py-3">
                  <input
                    type="text"
                    placeholder="암 연구에 대해 질문해보세요..."
                    className="flex-1 bg-transparent font-[family-name:var(--font-dm-sans)] text-sm outline-none placeholder:text-[var(--oaria-tagline)]"
                  />
                  <button className="w-8 h-8 bg-[var(--oaria-teal)] rounded-full flex items-center justify-center hover:bg-[var(--oaria-light-teal)] transition-colors">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M14 2L7 9M14 2L9.5 14L7 9M14 2L2 6.5L7 9" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-20 px-6 bg-gradient-to-b from-transparent to-[var(--oaria-teal)]/5">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <span className="font-[family-name:var(--font-dm-sans)] text-sm font-medium text-[var(--oaria-teal)] uppercase tracking-[0.15em]">Features</span>
            <h2 className="font-[family-name:var(--font-outfit)] text-3xl md:text-4xl font-bold text-[var(--foreground)] mt-4">
              연구를 더 스마트하게
            </h2>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {/* Feature 1 */}
            <div className="bg-[var(--background)] rounded-2xl border border-[var(--oaria-border)] p-8 hover:border-[var(--oaria-teal)]/50 transition-colors group">
              <div className="w-12 h-12 bg-[var(--oaria-teal)]/10 rounded-xl flex items-center justify-center mb-6 group-hover:bg-[var(--oaria-teal)]/20 transition-colors">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M21 21L15 15M17 10C17 13.866 13.866 17 10 17C6.13401 17 3 13.866 3 10C3 6.13401 6.13401 3 10 3C13.866 3 17 6.13401 17 10Z" stroke="var(--oaria-teal)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
              <h3 className="font-[family-name:var(--font-outfit)] text-xl font-semibold text-[var(--foreground)] mb-3">
                논문 검색 & 분석
              </h3>
              <p className="font-[family-name:var(--font-dm-sans)] text-[var(--oaria-text-secondary)] leading-relaxed">
                PubMed, Europe PMC 등 주요 의학 데이터베이스에서 최신 암 연구 논문을 실시간으로 검색하고 분석합니다.
              </p>
            </div>

            {/* Feature 2 */}
            <div className="bg-[var(--background)] rounded-2xl border border-[var(--oaria-border)] p-8 hover:border-[var(--oaria-teal)]/50 transition-colors group">
              <div className="w-12 h-12 bg-[var(--oaria-coral)]/10 rounded-xl flex items-center justify-center mb-6 group-hover:bg-[var(--oaria-coral)]/20 transition-colors">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="var(--oaria-coral)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  <path d="M2 17L12 22L22 17" stroke="var(--oaria-coral)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  <path d="M2 12L12 17L22 12" stroke="var(--oaria-coral)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
              <h3 className="font-[family-name:var(--font-outfit)] text-xl font-semibold text-[var(--foreground)] mb-3">
                RAG 기반 답변
              </h3>
              <p className="font-[family-name:var(--font-dm-sans)] text-[var(--oaria-text-secondary)] leading-relaxed">
                검증된 논문 데이터를 기반으로 정확하고 신뢰할 수 있는 답변을 제공합니다. 모든 답변에는 출처가 명시됩니다.
              </p>
            </div>

            {/* Feature 3 */}
            <div className="bg-[var(--background)] rounded-2xl border border-[var(--oaria-border)] p-8 hover:border-[var(--oaria-teal)]/50 transition-colors group">
              <div className="w-12 h-12 bg-[var(--oaria-light-teal)]/10 rounded-xl flex items-center justify-center mb-6 group-hover:bg-[var(--oaria-light-teal)]/20 transition-colors">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M9 5H7C5.89543 5 5 5.89543 5 7V19C5 20.1046 5.89543 21 7 21H17C18.1046 21 19 20.1046 19 19V7C19 5.89543 18.1046 5 17 5H15M9 5C9 6.10457 9.89543 7 11 7H13C14.1046 7 15 6.10457 15 5M9 5C9 3.89543 9.89543 3 11 3H13C14.1046 3 15 3.89543 15 5M12 12H15M12 16H15M9 12H9.01M9 16H9.01" stroke="var(--oaria-light-teal)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
              <h3 className="font-[family-name:var(--font-outfit)] text-xl font-semibold text-[var(--foreground)] mb-3">
                임상시험 연결
              </h3>
              <p className="font-[family-name:var(--font-dm-sans)] text-[var(--oaria-text-secondary)] leading-relaxed">
                현재 진행 중인 임상시험 정보를 제공하여 환자와 연구자가 최신 치료 옵션을 탐색할 수 있도록 돕습니다.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-16 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            <div className="text-center">
              <div className="font-[family-name:var(--font-outfit)] text-4xl md:text-5xl font-bold text-[var(--oaria-teal)]">5M+</div>
              <div className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] mt-2">논문 데이터</div>
            </div>
            <div className="text-center">
              <div className="font-[family-name:var(--font-outfit)] text-4xl md:text-5xl font-bold text-[var(--oaria-light-teal)]">100K+</div>
              <div className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] mt-2">임상시험</div>
            </div>
            <div className="text-center">
              <div className="font-[family-name:var(--font-outfit)] text-4xl md:text-5xl font-bold text-[var(--oaria-coral)]">99%</div>
              <div className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] mt-2">출처 정확도</div>
            </div>
            <div className="text-center">
              <div className="font-[family-name:var(--font-outfit)] text-4xl md:text-5xl font-bold text-[var(--oaria-navy)]">24/7</div>
              <div className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] mt-2">실시간 지원</div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-6">
        <div className="max-w-4xl mx-auto">
          <div className="bg-gradient-to-br from-[var(--oaria-teal)] to-[#0F766E] rounded-3xl p-12 text-center text-white">
            <h2 className="font-[family-name:var(--font-outfit)] text-3xl md:text-4xl font-bold mb-4">
              지금 시작하세요
            </h2>
            <p className="font-[family-name:var(--font-dm-sans)] text-white/80 max-w-xl mx-auto mb-8">
              OARIA와 함께 암 연구의 새로운 가능성을 탐색하세요.
              최신 연구 동향을 빠르게 파악하고 신뢰할 수 있는 정보를 얻으세요.
            </p>
            <button className="bg-white text-[var(--oaria-teal)] font-[family-name:var(--font-dm-sans)] font-medium px-8 py-4 rounded-full hover:bg-white/90 transition-colors">
              무료로 시작하기
            </button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 px-6 border-t border-[var(--oaria-border)]">
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            {/* Logo with Tagline - from oaria-logo-assets.html horizontal logo */}
            <svg width="120" height="36" viewBox="0 0 240 72" fill="none" xmlns="http://www.w3.org/2000/svg">
              {/* Triple Gate Icon */}
              <g transform="translate(3, 5)">
                <circle cx="31" cy="31" r="28" stroke="var(--oaria-light-ring)" strokeWidth="2" fill="none"/>
                <circle cx="31" cy="31" r="28" stroke="var(--oaria-teal)" strokeWidth="2.5" strokeDasharray="44 132" strokeLinecap="round" fill="none"/>
                <circle cx="31" cy="31" r="21" stroke="var(--oaria-light-ring)" strokeWidth="2" fill="none"/>
                <circle cx="31" cy="31" r="21" stroke="var(--oaria-light-teal)" strokeWidth="2.5" strokeDasharray="33 99" strokeLinecap="round" fill="none" transform="rotate(60 31 31)"/>
                <circle cx="31" cy="31" r="14" stroke="var(--oaria-light-ring)" strokeWidth="2" fill="none"/>
                <circle cx="31" cy="31" r="14" stroke="var(--oaria-coral)" strokeWidth="2.5" strokeDasharray="22 66" strokeLinecap="round" fill="none" transform="rotate(120 31 31)"/>
                <circle cx="31" cy="31" r="6.5" fill="var(--oaria-navy)"/>
                <circle cx="31" cy="31" r="3.25" fill="white"/>
              </g>
              {/* Text */}
              <g transform="translate(75, 18)">
                <text x="0" y="28" fontFamily="var(--font-outfit), Outfit, sans-serif" fontSize="36" fontWeight="600" fill="var(--oaria-teal)" letterSpacing="0.12em">OARIA</text>
                <text x="3.25" y="44" fontFamily="var(--font-dm-sans), DM Sans, sans-serif" fontSize="8.6" fontWeight="500" fill="var(--oaria-tagline)" textLength="123.5" lengthAdjust="spacing">RESEARCH INTELLIGENCE</text>
              </g>
            </svg>

            {/* Copyright */}
            <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-tagline)]">
              © 2025 OARIA. All rights reserved.
            </p>

            {/* Links */}
            <div className="flex items-center gap-6">
              <a href="#" className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] hover:text-[var(--oaria-teal)] transition-colors">
                Privacy
              </a>
              <a href="#" className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] hover:text-[var(--oaria-teal)] transition-colors">
                Terms
              </a>
              <a href="https://github.com" target="_blank" rel="noopener noreferrer" className="text-[var(--oaria-text-secondary)] hover:text-[var(--oaria-teal)] transition-colors">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z"/>
                </svg>
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

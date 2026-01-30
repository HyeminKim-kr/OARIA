"use client";

import { LogIn, X } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

interface LoginPromptModalProps {
  isOpen: boolean;
  onClose: () => void;
  message?: string;
}

export function LoginPromptModal({
  isOpen,
  onClose,
  message = "이 기능을 사용하려면 로그인이 필요합니다.",
}: LoginPromptModalProps) {
  const { login } = useAuth();

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        className="relative mx-4 w-full max-w-sm rounded-2xl bg-[var(--background)] p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute right-4 top-4 text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)]"
        >
          <X size={20} />
        </button>

        <div className="flex flex-col items-center text-center">
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-[var(--oaria-teal)]/10">
            <LogIn size={28} className="text-[var(--oaria-teal)]" />
          </div>

          <h3 className="mb-2 font-[family-name:var(--font-outfit)] text-lg font-semibold text-[var(--foreground)]">
            로그인이 필요합니다
          </h3>

          <p className="mb-6 text-sm text-[var(--oaria-text-secondary)]">
            {message}
          </p>

          <button
            onClick={() => {
              onClose();
              login();
            }}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-[var(--oaria-teal)] px-4 py-3 font-medium text-white transition-colors hover:bg-[var(--oaria-light-teal)]"
          >
            <LogIn size={18} />
            Google로 로그인
          </button>
        </div>
      </div>
    </div>
  );
}

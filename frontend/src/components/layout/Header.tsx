"use client";

import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { Moon, Bell, User, LogOut } from "lucide-react";

export function Header() {
  const { user, logout } = useAuth();

  return (
    <header className="fixed top-0 left-0 right-0 h-16 bg-[var(--background)] border-b-2 border-[var(--oaria-border-strong)] flex items-center justify-between px-8 z-50">
      {/* Logo - Left */}
      <Link href="/main" className="flex items-center gap-3">
        <svg
          width="36"
          height="36"
          viewBox="0 0 62 62"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <circle
            cx="31"
            cy="31"
            r="28"
            stroke="var(--oaria-light-ring)"
            strokeWidth="2"
            fill="none"
          />
          <circle
            cx="31"
            cy="31"
            r="28"
            stroke="var(--oaria-teal)"
            strokeWidth="2.5"
            strokeDasharray="44 132"
            strokeLinecap="round"
            fill="none"
          />
          <circle
            cx="31"
            cy="31"
            r="21"
            stroke="var(--oaria-light-ring)"
            strokeWidth="2"
            fill="none"
          />
          <circle
            cx="31"
            cy="31"
            r="21"
            stroke="var(--oaria-light-teal)"
            strokeWidth="2.5"
            strokeDasharray="33 99"
            strokeLinecap="round"
            fill="none"
            transform="rotate(60 31 31)"
          />
          <circle
            cx="31"
            cy="31"
            r="14"
            stroke="var(--oaria-light-ring)"
            strokeWidth="2"
            fill="none"
          />
          <circle
            cx="31"
            cy="31"
            r="14"
            stroke="var(--oaria-coral)"
            strokeWidth="2.5"
            strokeDasharray="22 66"
            strokeLinecap="round"
            fill="none"
            transform="rotate(120 31 31)"
          />
          <circle cx="31" cy="31" r="6.5" fill="var(--oaria-navy)" />
          <circle cx="31" cy="31" r="3.25" fill="white" />
        </svg>
        <span className="font-[family-name:var(--font-outfit)] text-xl font-semibold text-[var(--oaria-teal)] tracking-wider">
          OARIA
        </span>
      </Link>

      {/* Icons - Right */}
      <div className="flex items-center gap-2">
        {/* Dark Mode */}
        <button
          className="p-2.5 rounded-lg hover:bg-[var(--oaria-border)]/50 transition-colors text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)]"
          title="Dark mode"
        >
          <Moon size={20} />
        </button>

        {/* Notifications */}
        <button
          className="p-2.5 rounded-lg hover:bg-[var(--oaria-border)]/50 transition-colors text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)]"
          title="Notifications"
        >
          <Bell size={20} />
        </button>

        {/* Profile */}
        {user && (
          <>
            <button
              className="p-2.5 rounded-lg hover:bg-[var(--oaria-border)]/50 transition-colors text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)]"
              title="Profile"
            >
              {user.picture ? (
                <img
                  src={user.picture}
                  alt={user.name || "User"}
                  className="w-5 h-5 rounded-full"
                />
              ) : (
                <User size={20} />
              )}
            </button>

            {/* Logout */}
            <button
              onClick={logout}
              className="p-2.5 rounded-lg hover:bg-[var(--oaria-border)]/50 transition-colors text-[var(--oaria-text-secondary)] hover:text-[var(--oaria-coral)]"
              title="Logout"
            >
              <LogOut size={20} />
            </button>
          </>
        )}
      </div>
    </header>
  );
}

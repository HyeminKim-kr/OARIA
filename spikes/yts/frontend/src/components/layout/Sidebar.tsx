"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import {
  MessageSquare,
  FileText,
  Library,
  Bell,
  User,
  FlaskConical,
  MessageCircle,
  Moon,
  LogOut,
} from "lucide-react";

const mainNavItems = [
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/papers", label: "Papers", icon: FileText },
  { href: "/library", label: "My Library", icon: Library },
  { href: "/notifications", label: "Notifications", icon: Bell },
  { href: "/profile", label: "Profile", icon: User },
];

const bottomNavItems = [
  { href: "/labs", label: "Labs", icon: FlaskConical },
  { href: "/feedback", label: "Feedback", icon: MessageCircle },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-72 bg-[var(--background)] border-r border-[var(--oaria-border)] flex flex-col">
      {/* Logo */}
      <div className="p-5">
        <Link href="/chat" className="flex items-center gap-3">
          <svg
            width="40"
            height="40"
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
      </div>

      {/* Main Navigation */}
      <nav className="flex-1 px-4">
        <ul className="space-y-1.5">
          {mainNavItems.map((item) => {
            const isActive = pathname === item.href;
            const Icon = item.icon;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={`flex items-center gap-3 px-4 py-3 rounded-xl font-[family-name:var(--font-dm-sans)] text-sm transition-colors ${
                    isActive
                      ? "bg-[var(--oaria-teal)]/10 text-[var(--oaria-teal)] font-medium"
                      : "text-[var(--oaria-text-secondary)] hover:bg-[var(--oaria-border)]/50 hover:text-[var(--foreground)]"
                  }`}
                >
                  <Icon size={20} />
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Bottom Navigation */}
      <div className="px-4 pb-4">
        <ul className="space-y-1.5 border-t border-[var(--oaria-border)] pt-4">
          {bottomNavItems.map((item) => {
            const Icon = item.icon;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className="flex items-center gap-3 px-4 py-3 rounded-xl font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] hover:bg-[var(--oaria-border)]/50 hover:text-[var(--foreground)] transition-colors"
                >
                  <Icon size={20} />
                  {item.label}
                </Link>
              </li>
            );
          })}
          <li>
            <button className="w-full flex items-center gap-3 px-4 py-3 rounded-xl font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)] hover:bg-[var(--oaria-border)]/50 hover:text-[var(--foreground)] transition-colors">
              <Moon size={20} />
              Dark mode
            </button>
          </li>
        </ul>

        {/* User Info */}
        {user && (
          <div className="mt-4 p-3 rounded-xl bg-[var(--oaria-border)]/30">
            <div className="flex items-center gap-3">
              {user.picture ? (
                <img
                  src={user.picture}
                  alt={user.name || "User"}
                  className="w-10 h-10 rounded-full"
                />
              ) : (
                <div className="w-10 h-10 rounded-full bg-[var(--oaria-teal)] flex items-center justify-center text-white font-medium">
                  {user.name?.charAt(0) || user.email.charAt(0)}
                </div>
              )}
              <div className="flex-1 min-w-0">
                <p className="font-[family-name:var(--font-dm-sans)] text-sm font-medium truncate">
                  {user.name || "User"}
                </p>
                <p className="font-[family-name:var(--font-dm-sans)] text-xs text-[var(--oaria-tagline)] truncate">
                  {user.email}
                </p>
              </div>
              <button
                onClick={logout}
                className="p-2 rounded-lg hover:bg-[var(--oaria-border)] transition-colors text-[var(--oaria-text-secondary)] hover:text-[var(--oaria-coral)]"
                title="Logout"
              >
                <LogOut size={18} />
              </button>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}

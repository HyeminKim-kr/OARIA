'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Search,
  FileText,
  Clock,
  Users,
  FlaskConical,
  Database,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuth } from '@/contexts/AuthContext';

interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  superAdminOnly?: boolean;
}

const navigation: NavItem[] = [
  { name: '대시보드', href: '/', icon: LayoutDashboard },
  { name: '검색 쿼리', href: '/queries', icon: Search },
  { name: '수집 작업', href: '/jobs', icon: Clock },
  { name: '논문 목록', href: '/papers', icon: FileText },
  { name: '임베딩 관리', href: '/embeddings', icon: Database },
  { name: 'RAG Lab', href: '/lab', icon: FlaskConical },
  { name: '관리자 관리', href: '/admin-users', icon: Users, superAdminOnly: true },
];

export function Sidebar() {
  const pathname = usePathname();
  const { isSuperAdmin } = useAuth();

  const filteredNavigation = navigation.filter(
    (item) => !item.superAdminOnly || isSuperAdmin
  );

  return (
    <div className="flex h-full w-64 flex-col bg-gray-900">
      <div className="flex h-16 items-center px-6">
        <h1 className="text-xl font-bold text-white">OARIA Admin</h1>
      </div>
      <nav className="flex-1 space-y-1 px-3 py-4">
        {filteredNavigation.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                'group flex items-center rounded-md px-3 py-2 text-sm font-medium',
                isActive
                  ? 'bg-gray-800 text-white'
                  : 'text-gray-300 hover:bg-gray-700 hover:text-white'
              )}
            >
              <item.icon
                className={cn(
                  'mr-3 h-5 w-5 flex-shrink-0',
                  isActive ? 'text-white' : 'text-gray-400 group-hover:text-white'
                )}
              />
              {item.name}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-gray-700 p-4">
        <p className="text-xs text-gray-500">Cancer Paper Collector v1.0</p>
      </div>
    </div>
  );
}

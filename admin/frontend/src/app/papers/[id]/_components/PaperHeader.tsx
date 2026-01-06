'use client';

import { ArrowLeft } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { Paper } from '@/lib/api';

interface PaperHeaderProps {
  paper: Paper;
}

export function PaperHeader({ paper }: PaperHeaderProps) {
  const router = useRouter();

  return (
    <div className="flex items-center gap-4">
      <button onClick={() => router.back()} className="rounded-full p-2 hover:bg-gray-100">
        <ArrowLeft className="h-5 w-5" />
      </button>
      <div className="flex-1">
        <h1 className="text-xl font-bold text-gray-900">{paper.title}</h1>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-gray-500">
          {paper.journal && <span>{paper.journal}</span>}
          {paper.year && <span>({paper.year})</span>}
          <StatusBadge status={paper.status} />
        </div>
      </div>
    </div>
  );
}

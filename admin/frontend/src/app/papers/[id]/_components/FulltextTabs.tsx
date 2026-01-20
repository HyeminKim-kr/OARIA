'use client';

import { useState } from 'react';
import { FileText, Code, Layers } from 'lucide-react';
import { PaperFulltext } from '@/lib/api';

type TabType = 'fulltext' | 'display' | 'xml';

interface FulltextTabsProps {
  data?: PaperFulltext;
  isLoading: boolean;
}

export function FulltextTabs({ data, isLoading }: FulltextTabsProps) {
  const [activeTab, setActiveTab] = useState<TabType>('fulltext');

  return (
    <div className="rounded-lg bg-white shadow">
      <div className="border-b border-gray-200">
        <nav className="flex">
          <button
            onClick={() => setActiveTab('fulltext')}
            className={`flex items-center gap-2 px-6 py-3 text-sm font-medium ${
              activeTab === 'fulltext'
                ? 'border-b-2 border-blue-500 text-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <FileText className="h-4 w-4" />
            Full Text
          </button>
          <button
            onClick={() => setActiveTab('display')}
            className={`flex items-center gap-2 px-6 py-3 text-sm font-medium ${
              activeTab === 'display'
                ? 'border-b-2 border-green-500 text-green-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <Layers className="h-4 w-4" />
            Display
            {data?.display && (
              <span className="ml-1 rounded bg-green-100 px-1.5 py-0.5 text-xs text-green-700">
                {data.display.sections?.length || 0}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('xml')}
            className={`flex items-center gap-2 px-6 py-3 text-sm font-medium ${
              activeTab === 'xml'
                ? 'border-b-2 border-blue-500 text-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <Code className="h-4 w-4" />
            Raw XML
          </button>
        </nav>
      </div>

      <div className="p-6">
        {isLoading ? (
          <div className="animate-pulse">
            <div className="mb-2 h-4 w-full rounded bg-gray-200" />
            <div className="mb-2 h-4 w-5/6 rounded bg-gray-200" />
            <div className="h-4 w-4/6 rounded bg-gray-200" />
          </div>
        ) : activeTab === 'fulltext' ? (
          data?.fulltext ? (
            <pre className="max-h-[600px] overflow-auto whitespace-pre-wrap font-sans text-sm leading-relaxed text-gray-700">
              {data.fulltext}
            </pre>
          ) : (
            <p className="py-8 text-center text-gray-500">Full text not available</p>
          )
        ) : activeTab === 'display' ? (
          data?.display ? (
            <div className="max-h-[600px] space-y-6 overflow-auto">
              {data.display.sections.map((section, sIdx) => (
                <div key={sIdx} className="overflow-hidden rounded-lg border">
                  <div className="flex items-center gap-2 bg-gray-100 px-4 py-2">
                    <span className="rounded bg-blue-100 px-2 py-0.5 font-mono text-xs text-blue-700">
                      {section.name}
                    </span>
                    <span className="font-medium text-gray-900">{section.title}</span>
                    <span className="text-xs text-gray-500">
                      ({section.paragraphs?.length || 0} paragraphs)
                    </span>
                  </div>
                  <div className="space-y-3 p-4">
                    {section.paragraphs?.map((para, pIdx) => (
                      <p key={pIdx} className="text-sm leading-relaxed text-gray-700">
                        {para.text}
                      </p>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="py-8 text-center text-gray-500">
              Display data not available (논문 재수집 필요)
            </p>
          )
        ) : data?.rawXml ? (
          <pre className="max-h-[600px] overflow-auto rounded bg-gray-50 p-4 font-mono text-xs text-gray-700">
            {data.rawXml}
          </pre>
        ) : (
          <p className="py-8 text-center text-gray-500">Raw XML not available</p>
        )}
      </div>
    </div>
  );
}

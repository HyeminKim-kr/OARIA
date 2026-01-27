"use client";

import { useMemo, useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  Search,
  Bot,
  MessageSquare,
  BarChart3,
  FileText,
  BookOpen,
  Users,
  Tag,
  Loader2,
  X,
} from "lucide-react";
import { dashboardApi, Paper } from "@/lib/api";
import { PASTEL } from "./constants";

// D3 chart components
import StreamGraph from "./components/StreamGraph";
import BubbleChart, { BubbleData } from "./components/BubbleChart";
import NetworkGraph from "./components/NetworkGraph";
import HeatmapChart from "./components/HeatmapChart";
import DonutChart from "./components/DonutChart";
import TopJournalsBar from "./components/TopJournalsBar";
import KeywordTreemap from "./components/KeywordTreemap";
import RadialYearChart from "./components/RadialYearChart";
import TopAuthorsBar from "./components/TopAuthorsBar";
import PaperTimeline from "./components/PaperTimeline";

// ─────────────────────────────────────────────────────
// Data processing helpers
// ─────────────────────────────────────────────────────

function processStreamData(papers: Paper[]) {
  const kwCounts: Record<string, number> = {};
  papers.forEach((p) =>
    p.keywords?.forEach((kw) => {
      const k = kw.trim();
      if (k) kwCounts[k] = (kwCounts[k] || 0) + 1;
    })
  );
  const topKW = Object.entries(kwCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([k]) => k);

  const yearMap: Record<number, Record<string, number>> = {};
  papers.forEach((p) => {
    if (!p.year) return;
    if (!yearMap[p.year]) yearMap[p.year] = {};
    p.keywords?.forEach((kw) => {
      const k = kw.trim();
      if (topKW.includes(k)) yearMap[p.year!][k] = (yearMap[p.year!][k] || 0) + 1;
    });
  });

  const data = Object.entries(yearMap)
    .map(([year, kws]) => ({
      year: parseInt(year),
      ...Object.fromEntries(topKW.map((k) => [k, kws[k] || 0])),
    }))
    .sort((a, b) => a.year - b.year);

  return { data, keys: topKW };
}

function processBubbleData(papers: Paper[]): BubbleData[] {
  const now = new Date();
  const halfYear = new Date(now.getTime() - 180 * 86400000);

  const kwTotal: Record<string, number> = {};
  const kwRecent: Record<string, number> = {};

  papers.forEach((p) => {
    const isRecent = p.created_at ? new Date(p.created_at) > halfYear : false;
    p.keywords?.forEach((kw) => {
      const k = kw.trim();
      if (!k) return;
      kwTotal[k] = (kwTotal[k] || 0) + 1;
      if (isRecent) kwRecent[k] = (kwRecent[k] || 0) + 1;
    });
  });

  return Object.entries(kwTotal)
    .map(([keyword, count]) => {
      const recent = kwRecent[keyword] || 0;
      const older = count - recent;
      const growth = older > 0 ? ((recent - older) / older) * 100 : recent > 0 ? 100 : 0;
      return { keyword, count, growth };
    })
    .sort((a, b) => b.count - a.count)
    .slice(0, 25);
}

function processNetworkData(papers: Paper[]) {
  const kwCounts: Record<string, number> = {};
  const edgeCounts: Record<string, number> = {};

  papers.forEach((p) => {
    const kws = (p.keywords || []).map((k) => k.trim()).filter(Boolean);
    kws.forEach((k) => (kwCounts[k] = (kwCounts[k] || 0) + 1));
    for (let i = 0; i < kws.length; i++) {
      for (let j = i + 1; j < kws.length; j++) {
        const key = [kws[i], kws[j]].sort().join("||");
        edgeCounts[key] = (edgeCounts[key] || 0) + 1;
      }
    }
  });

  const topKW = Object.entries(kwCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 20)
    .map(([k]) => k);
  const topSet = new Set(topKW);

  const nodes = topKW.map((id) => ({ id, count: kwCounts[id] }));
  const links = Object.entries(edgeCounts)
    .filter(([key]) => {
      const [a, b] = key.split("||");
      return topSet.has(a) && topSet.has(b);
    })
    .map(([key, weight]) => {
      const [source, target] = key.split("||");
      return { source, target, weight };
    })
    .sort((a, b) => b.weight - a.weight)
    .slice(0, 50);

  return { nodes, links };
}

function processHeatmapData(papers: Paper[]) {
  const jCount: Record<string, number> = {};
  papers.forEach((p) => {
    if (p.journal) jCount[p.journal] = (jCount[p.journal] || 0) + 1;
  });
  const topJ = Object.entries(jCount)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([j]) => j);
  const topJSet = new Set(topJ);

  const cells: Record<string, { journal: string; year: number; count: number }> = {};
  papers.forEach((p) => {
    if (!p.journal || !p.year || !topJSet.has(p.journal)) return;
    const key = `${p.journal}__${p.year}`;
    if (!cells[key]) cells[key] = { journal: p.journal, year: p.year, count: 0 };
    cells[key].count++;
  });

  return Object.values(cells);
}

function processDonutData(papers: Paper[]) {
  let oa = 0;
  let closed = 0;
  papers.forEach((p) => {
    if (p.is_open_access) oa++;
    else closed++;
  });
  return [
    { label: "Open Access", value: oa },
    { label: "Closed", value: closed },
  ].filter((d) => d.value > 0);
}

function processTopJournals(papers: Paper[]) {
  const counts: Record<string, number> = {};
  papers.forEach((p) => {
    if (p.journal) counts[p.journal] = (counts[p.journal] || 0) + 1;
  });
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([label, value]) => ({ label, value }));
}

function processTopAuthors(papers: Paper[]) {
  const counts: Record<string, number> = {};
  papers.forEach((p) => {
    p.authors?.forEach((a) => {
      if (a.author_name) counts[a.author_name] = (counts[a.author_name] || 0) + 1;
    });
  });
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([label, value]) => ({ label, value }));
}

function processTreemapData(papers: Paper[]) {
  const counts: Record<string, number> = {};
  papers.forEach((p) =>
    p.keywords?.forEach((kw) => {
      const k = kw.trim();
      if (k) counts[k] = (counts[k] || 0) + 1;
    })
  );
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 30)
    .map(([name, value]) => ({ name, value }));
}

function processTimelineData(papers: Paper[]) {
  return papers
    .filter((p) => p.created_at)
    .slice(0, 15)
    .map((p) => ({
      id: p.id,
      title: p.title,
      journal: p.journal || "",
      date: p.created_at,
    }));
}

// ─────────────────────────────────────────────────────
// Animated counter
// ─────────────────────────────────────────────────────

function AnimatedCounter({
  value,
  duration = 1500,
}: {
  value: number;
  duration?: number;
}) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    const start = performance.now();
    function tick(now: number) {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(value * eased));
      if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }, [value, duration]);
  return <>{display.toLocaleString()}</>;
}

// ─────────────────────────────────────────────────────
// Chart section wrapper
// ─────────────────────────────────────────────────────

function ChartSection({
  title,
  subtitle,
  children,
  className = "",
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-2xl border border-[var(--oaria-border)] bg-[var(--background)] p-5 transition-shadow hover:shadow-lg hover:shadow-[var(--oaria-border)]/20 ${className}`}
    >
      <div className="mb-3">
        <h3 className="font-[family-name:var(--font-outfit)] text-base font-semibold">
          {title}
        </h3>
        {subtitle && (
          <p className="text-xs text-[var(--oaria-text-secondary)] mt-0.5">
            {subtitle}
          </p>
        )}
      </div>
      {children}
    </div>
  );
}

// ─────────────────────────────────────────────────────
// Keyword Modal
// ─────────────────────────────────────────────────────

function KeywordModal({
  keyword,
  papers,
  onClose,
}: {
  keyword: string;
  papers: Paper[];
  onClose: () => void;
}) {
  const related = papers.filter((p) =>
    p.keywords?.some((k) => k.toLowerCase() === keyword.toLowerCase())
  );

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/25 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-[var(--background)] rounded-2xl border border-[var(--oaria-border)] p-6 max-w-lg w-full max-h-[70vh] overflow-y-auto shadow-2xl mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="font-[family-name:var(--font-outfit)] text-lg font-semibold">
              &ldquo;{keyword}&rdquo;
            </h3>
            <p className="text-sm text-[var(--oaria-text-secondary)]">
              관련 논문 {related.length}건
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-[var(--oaria-border)]/50 transition-colors"
          >
            <X size={18} />
          </button>
        </div>
        <div className="space-y-3">
          {related.slice(0, 15).map((p) => (
            <Link
              key={p.id}
              href={`/papers/${p.id}`}
              className="block p-3 rounded-xl border border-[var(--oaria-border)] hover:border-[var(--oaria-teal)] transition-colors"
            >
              <p className="text-sm font-medium line-clamp-2">{p.title}</p>
              <p className="text-xs text-[var(--oaria-text-secondary)] mt-1">
                {p.journal || "Unknown"} {p.year ? `· ${p.year}` : ""}
              </p>
            </Link>
          ))}
          {related.length === 0 && (
            <p className="text-sm text-[var(--oaria-text-secondary)] py-4 text-center">
              관련 논문이 없습니다
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────
// Main Dashboard Page
// ─────────────────────────────────────────────────────

export default function DashboardPage() {
  const router = useRouter();
  const [selectedKeyword, setSelectedKeyword] = useState<string | null>(null);

  // Data queries
  const statsQuery = useQuery({
    queryKey: ["dashboard", "stats"],
    queryFn: dashboardApi.getPaperStats,
  });

  const papersQuery = useQuery({
    queryKey: ["dashboard", "analysisPapers"],
    queryFn: () => dashboardApi.getAnalysisPapers(200),
  });

  const papers = papersQuery.data || [];

  // Processed data
  const streamData = useMemo(() => processStreamData(papers), [papers]);
  const bubbleData = useMemo(() => processBubbleData(papers), [papers]);
  const networkData = useMemo(() => processNetworkData(papers), [papers]);
  const heatmapData = useMemo(() => processHeatmapData(papers), [papers]);
  const donutData = useMemo(() => processDonutData(papers), [papers]);
  const topJournals = useMemo(() => processTopJournals(papers), [papers]);
  const topAuthors = useMemo(() => processTopAuthors(papers), [papers]);
  const treemapData = useMemo(() => processTreemapData(papers), [papers]);
  const timelineData = useMemo(() => processTimelineData(papers), [papers]);
  const radialData = useMemo(
    () =>
      statsQuery.data?.by_year
        ? [...statsQuery.data.by_year].reverse()
        : [],
    [statsQuery.data]
  );

  // Derived stats
  const totalPapers = statsQuery.data?.total || 0;
  const recentCount = statsQuery.data?.recent_count || 0;
  const uniqueKeywords = useMemo(() => {
    const set = new Set<string>();
    papers.forEach((p) => p.keywords?.forEach((k) => set.add(k.trim())));
    return set.size;
  }, [papers]);
  const uniqueJournals = useMemo(() => {
    const set = new Set<string>();
    papers.forEach((p) => {
      if (p.journal) set.add(p.journal);
    });
    return set.size;
  }, [papers]);

  const handleKeywordClick = useCallback((keyword: string) => {
    setSelectedKeyword(keyword);
  }, []);

  const handlePaperClick = useCallback(
    (id: string) => {
      router.push(`/papers/${id}`);
    },
    [router]
  );

  const isLoading = statsQuery.isLoading || papersQuery.isLoading;

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header Tabs */}
      <div className="bg-[var(--background)]">
        <div className="flex items-center justify-center">
          <div className="flex items-center gap-6">
            <Link
              href="/ask"
              className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-colors"
            >
              <MessageSquare size={20} />
              Ask AI
            </Link>
            <Link
              href="/main"
              className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-colors"
            >
              <Search size={20} />
              Search Papers
            </Link>
            <Link
              href="/agents"
              className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-colors"
            >
              <Bot size={20} />
              Agents
            </Link>
            <button
              type="button"
              className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-[var(--oaria-teal)] text-[var(--oaria-teal)]"
            >
              <BarChart3 size={20} />
              Dashboard
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-[1400px] mx-auto px-6 py-8">
          {/* Title */}
          <div className="mb-8">
            <h1 className="font-[family-name:var(--font-outfit)] text-3xl font-semibold mb-1">
              Research Intelligence
            </h1>
            <p className="font-[family-name:var(--font-dm-sans)] text-base text-[var(--oaria-text-secondary)]">
              연구 지형을 내려다보는 관점
            </p>
          </div>

          {/* Loading overlay */}
          {isLoading && (
            <div className="flex items-center justify-center py-20">
              <div className="flex flex-col items-center gap-3">
                <Loader2 size={32} className="animate-spin text-[var(--oaria-teal)]" />
                <p className="text-sm text-[var(--oaria-text-secondary)]">
                  데이터를 분석하고 있습니다...
                </p>
              </div>
            </div>
          )}

          {!isLoading && (
            <>
              {/* ─── Row 1: Hero Stat Cards ─── */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                {[
                  {
                    icon: <FileText size={20} />,
                    color: PASTEL[0],
                    label: "Total Papers",
                    value: totalPapers,
                    sub: `최근 7일 +${recentCount}`,
                  },
                  {
                    icon: <BookOpen size={20} />,
                    color: PASTEL[1],
                    label: "This Week",
                    value: recentCount,
                    sub: "새로 수집된 논문",
                  },
                  {
                    icon: <Tag size={20} />,
                    color: PASTEL[3],
                    label: "Keywords",
                    value: uniqueKeywords,
                    sub: "고유 키워드 수",
                  },
                  {
                    icon: <Users size={20} />,
                    color: PASTEL[4],
                    label: "Journals",
                    value: uniqueJournals,
                    sub: "수록 저널 수",
                  },
                ].map((card) => (
                  <div
                    key={card.label}
                    className="p-5 rounded-2xl border border-[var(--oaria-border)] bg-[var(--background)] transition-all hover:shadow-lg hover:shadow-[var(--oaria-border)]/20 hover:-translate-y-0.5"
                  >
                    <div className="flex items-center gap-3 mb-3">
                      <div
                        className="w-9 h-9 rounded-lg flex items-center justify-center"
                        style={{ backgroundColor: card.color + "25", color: card.color }}
                      >
                        {card.icon}
                      </div>
                      <span className="text-sm text-[var(--oaria-text-secondary)] font-medium">
                        {card.label}
                      </span>
                    </div>
                    <p className="font-[family-name:var(--font-outfit)] text-3xl font-bold">
                      <AnimatedCounter value={card.value} />
                    </p>
                    <p className="text-xs text-[var(--oaria-text-secondary)] mt-1">
                      {card.sub}
                    </p>
                  </div>
                ))}
              </div>

              {/* ─── Row 2: StreamGraph (full width) ─── */}
              <ChartSection
                title="Research Trend Stream"
                subtitle="연도별 핵심 키워드 트렌드 (Streamgraph)"
                className="mb-6"
              >
                <div className="h-72">
                  <StreamGraph
                    data={streamData.data}
                    keys={streamData.keys}
                  />
                </div>
              </ChartSection>

              {/* ─── Row 3: Bubble + Network ─── */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                <ChartSection
                  title="Hot Topics"
                  subtitle="키워드 빈도 + 성장률 (클릭하면 관련 논문)"
                >
                  <div className="h-80">
                    <BubbleChart
                      data={bubbleData}
                      onKeywordClick={handleKeywordClick}
                    />
                  </div>
                </ChartSection>

                <ChartSection
                  title="Keyword Network"
                  subtitle="키워드 동시 출현 관계 (클릭하면 관련 논문)"
                >
                  <div className="h-80">
                    <NetworkGraph
                      nodes={networkData.nodes}
                      links={networkData.links}
                      onNodeClick={handleKeywordClick}
                    />
                  </div>
                </ChartSection>
              </div>

              {/* ─── Row 4: Heatmap + (Journals + Donut) ─── */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                <ChartSection
                  title="Journal x Year Heatmap"
                  subtitle="저널별 연도 분포"
                >
                  <div className="h-72">
                    <HeatmapChart data={heatmapData} />
                  </div>
                </ChartSection>

                <div className="grid grid-rows-2 gap-6">
                  <ChartSection
                    title="Top 10 Journals"
                    subtitle="논문 수 기준"
                  >
                    <div className="h-48">
                      <TopJournalsBar data={topJournals} />
                    </div>
                  </ChartSection>

                  <ChartSection
                    title="Open Access"
                    subtitle="접근 유형 분포"
                  >
                    <div className="h-40">
                      <DonutChart data={donutData} centerLabel="Access" />
                    </div>
                  </ChartSection>
                </div>
              </div>

              {/* ─── Row 5: Treemap + Timeline ─── */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                <ChartSection
                  title="Keyword Landscape"
                  subtitle="키워드 빈도 트리맵 (클릭하면 관련 논문)"
                >
                  <div className="h-72">
                    <KeywordTreemap
                      data={treemapData}
                      onKeywordClick={handleKeywordClick}
                    />
                  </div>
                </ChartSection>

                <ChartSection
                  title="Recent Papers Timeline"
                  subtitle="최근 수집 논문 타임라인"
                >
                  <div className="h-72">
                    <PaperTimeline
                      data={timelineData}
                      onPaperClick={handlePaperClick}
                    />
                  </div>
                </ChartSection>
              </div>

              {/* ─── Row 6: Radial + Authors ─── */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                <ChartSection
                  title="Year Distribution"
                  subtitle="연도별 논문 분포 (Radial)"
                >
                  <div className="h-72">
                    <RadialYearChart data={radialData} />
                  </div>
                </ChartSection>

                <ChartSection
                  title="Top Authors"
                  subtitle="논문 수 기준 상위 저자"
                >
                  <div className="h-72">
                    <TopAuthorsBar data={topAuthors} />
                  </div>
                </ChartSection>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Keyword Modal */}
      {selectedKeyword && (
        <KeywordModal
          keyword={selectedKeyword}
          papers={papers}
          onClose={() => setSelectedKeyword(null)}
        />
      )}
    </div>
  );
}

"use client";

import { useMemo, useState, useEffect, useCallback } from "react";
import Link from "next/link";
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
  Database,
  FlaskConical,
} from "lucide-react";
import { dashboardApi, Paper } from "@/lib/api";
import { PASTEL } from "./constants";

// ─────────────────────────────────────────────────────
// Mock data generator
// ─────────────────────────────────────────────────────

const MOCK_KEYWORDS = [
  "Vector Embedding", "Chunking", "RAG", "Semantic Search", "Fine-tuning",
  "Transformer", "LLM", "Tokenization", "Prompt Engineering", "RLHF",
  "Knowledge Graph", "Named Entity Recognition", "Text Classification",
  "Attention Mechanism", "Few-shot Learning", "Zero-shot Learning",
  "Retrieval-Augmented Generation", "Sentence Embedding", "BM25",
  "Cross-Encoder", "Bi-Encoder", "Hallucination Detection",
  "Chain-of-Thought", "Multi-modal", "Document Parsing",
  "Hybrid Search", "Reranking", "Context Window", "Agentic AI", "Tool Use",
];

const MOCK_JOURNALS = [
  "Nature", "Science", "Cell", "PNAS", "Nature Medicine",
  "The Lancet", "NEJM", "BMJ", "Nature Biotechnology", "Cancer Research",
  "Genome Biology", "Molecular Cell", "Nature Genetics", "Blood", "JAMA",
  "Cell Reports", "eLife", "PLoS ONE", "Nucleic Acids Research", "Bioinformatics",
];

const MOCK_AUTHORS_WITH_AFF: { name: string; aff: string }[] = [
  { name: "Zhang Y.", aff: "Peking University, Beijing, China" },
  { name: "Wang L.", aff: "Shanghai Jiao Tong University, Shanghai, China" },
  { name: "Chen X.", aff: "Xiamen University, Xiamen, China" },
  { name: "Li J.", aff: "Fudan University, Shanghai, China" },
  { name: "Liu H.", aff: "Tsinghua University, Beijing, China" },
  { name: "Kim S.", aff: "Seoul National University, Seoul, South Korea" },
  { name: "Park J.", aff: "KAIST, Daejeon, South Korea" },
  { name: "Tanaka K.", aff: "University of Tokyo, Tokyo, Japan" },
  { name: "Smith J.", aff: "Harvard Medical School, Boston, USA" },
  { name: "Johnson M.", aff: "Stanford University, USA" },
  { name: "Brown A.", aff: "University of Cambridge, UK" },
  { name: "Lee D.", aff: "MIT, Cambridge, USA" },
  { name: "Yang W.", aff: "National University of Singapore, Singapore" },
  { name: "Wu Q.", aff: "University of Melbourne, Melbourne, Australia" },
  { name: "Patel R.", aff: "All India Institute of Medical Sciences, Delhi, India" },
  { name: "Garcia M.", aff: "Hospital Clínic, Barcelona, Spain" },
  { name: "Müller T.", aff: "Charité, Berlin, Germany" },
  { name: "Singh P.", aff: "University of Toronto, Toronto, Canada" },
  { name: "Anderson B.", aff: "Karolinska Institute, Stockholm, Sweden" },
  { name: "Taylor C.", aff: "Francis Crick Institute, London, UK" },
];

function generateMockPapers(count: number): Paper[] {
  const papers: Paper[] = [];
  const baseDate = new Date("2020-01-01");
  for (let i = 0; i < count; i++) {
    const year = 2020 + Math.floor(Math.random() * 6); // 2020-2025
    const kwCount = 2 + Math.floor(Math.random() * 4);
    const kwSet = new Set<string>();
    while (kwSet.size < kwCount) kwSet.add(MOCK_KEYWORDS[Math.floor(Math.random() * MOCK_KEYWORDS.length)]);
    const authCount = 1 + Math.floor(Math.random() * 6);
    const authors = Array.from({ length: authCount }, (_, j) => {
      const a = MOCK_AUTHORS_WITH_AFF[Math.floor(Math.random() * MOCK_AUTHORS_WITH_AFF.length)];
      return {
        author_name: a.name,
        author_order: j + 1,
        is_corresponding: j === 0,
        affiliation: a.aff,
      };
    });
    const daysOffset = Math.floor(Math.random() * 2000);
    const created = new Date(baseDate.getTime() + daysOffset * 86400000);
    papers.push({
      id: `mock-${i}`,
      paper_id: `mock:${i}`,
      title: `Mock Paper ${i + 1}: ${[...kwSet].slice(0, 2).join(" and ")} Research`,
      journal: MOCK_JOURNALS[Math.floor(Math.random() * MOCK_JOURNALS.length)],
      year,
      keywords: [...kwSet],
      is_open_access: Math.random() > 0.3,
      created_at: created.toISOString(),
      authors,
    });
  }
  return papers;
}

const MOCK_STATS = {
  total: 12403,
  recent_count: 187,
  by_year: [
    { year: 2020, count: 1420 },
    { year: 2021, count: 1980 },
    { year: 2022, count: 2340 },
    { year: 2023, count: 2870 },
    { year: 2024, count: 3150 },
    { year: 2025, count: 643 },
  ],
};

let _cachedMockPapers: Paper[] | null = null;
function getMockPapers() {
  if (!_cachedMockPapers) _cachedMockPapers = generateMockPapers(800);
  return _cachedMockPapers;
}

// D3 chart components
import BumpChart from "./components/BumpChart";
import BubbleChart, { BubbleData } from "./components/BubbleChart";
import NetworkGraph from "./components/NetworkGraph";
import HeatmapChart from "./components/HeatmapChart";
// DonutChart removed - replaced with DataQualityRadar
import JournalLollipop from "./components/JournalLollipop";
import JournalTreemap from "./components/JournalTreemap";
import RadialYearChart from "./components/RadialYearChart";
import TopAuthorsBar from "./components/TopAuthorsBar";
import WorldMap, { COUNTRY_COORDS } from "./components/WorldMap";
import type { CountryData } from "./components/WorldMap";
import DataQualityRadar from "./components/DataQualityRadar";
import type { DataQualityMetric } from "./components/DataQualityRadar";

// ─────────────────────────────────────────────────────
// Case-insensitive keyword normalization
// ─────────────────────────────────────────────────────

/**
 * Merge keywords that differ only by case.
 * Keeps the most-used casing as the canonical form.
 */
function buildCaseMap(papers: Paper[]): Record<string, string> {
  const rawCounts: Record<string, number> = {};
  papers.forEach((p) =>
    p.keywords?.forEach((kw) => {
      const k = kw.trim();
      if (k) rawCounts[k] = (rawCounts[k] || 0) + 1;
    })
  );
  // Group by lowercase, pick highest-count form
  const groups: Record<string, { form: string; count: number }> = {};
  for (const [form, count] of Object.entries(rawCounts)) {
    const lower = form.toLowerCase();
    if (!groups[lower] || count > groups[lower].count) {
      groups[lower] = { form, count };
    }
  }
  const map: Record<string, string> = {};
  for (const [form] of Object.entries(rawCounts)) {
    map[form] = groups[form.toLowerCase()].form;
  }
  return map;
}

function normalizeKw(kw: string, caseMap: Record<string, string>): string {
  const trimmed = kw.trim();
  return caseMap[trimmed] || trimmed;
}

// ─────────────────────────────────────────────────────
// Data processing helpers
// ─────────────────────────────────────────────────────

function processBumpData(papers: Paper[], caseMap: Record<string, string>) {
  // Count keywords first
  const kwCounts: Record<string, number> = {};
  papers.forEach((p) =>
    p.keywords?.forEach((kw) => {
      const k = normalizeKw(kw, caseMap);
      if (k) kwCounts[k] = (kwCounts[k] || 0) + 1;
    })
  );

  const totalKeywords = Object.values(kwCounts).reduce((a, b) => a + b, 0);

  // If keywords are too sparse, fall back to journals
  const useJournals = totalKeywords < papers.length * 0.3;

  let topItems: string[];
  let dataType: "keyword" | "journal";

  if (useJournals) {
    // Fall back to journals
    dataType = "journal";
    const journalCounts: Record<string, number> = {};
    papers.forEach((p) => {
      if (p.journal) journalCounts[p.journal] = (journalCounts[p.journal] || 0) + 1;
    });
    topItems = Object.entries(journalCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([j]) => j);
  } else {
    dataType = "keyword";
    topItems = Object.entries(kwCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([k]) => k);
  }

  // Determine time resolution
  const years = papers.map((p) => p.year).filter(Boolean) as number[];
  if (years.length === 0) return { items: [], keywords: [], periods: [], dataType: "keyword" as const };

  const minYear = Math.min(...years);
  const maxYear = Math.max(...years);
  const useMonthly = (maxYear - minYear) <= 3;

  // Build period → item → count
  const periodItemCount: Record<string, Record<string, number>> = {};

  if (useMonthly) {
    papers.forEach((p) => {
      if (!p.created_at) return;
      const d = new Date(p.created_at);
      const yr = d.getFullYear();
      const mo = String(d.getMonth() + 1).padStart(2, "0");
      const period = `${yr}.${mo}`;
      if (!periodItemCount[period]) periodItemCount[period] = {};

      if (useJournals) {
        if (p.journal && topItems.includes(p.journal)) {
          periodItemCount[period][p.journal] = (periodItemCount[period][p.journal] || 0) + 1;
        }
      } else {
        p.keywords?.forEach((kw) => {
          const k = normalizeKw(kw, caseMap);
          if (topItems.includes(k)) periodItemCount[period][k] = (periodItemCount[period][k] || 0) + 1;
        });
      }
    });
  } else {
    papers.forEach((p) => {
      if (!p.year) return;
      const period = String(p.year);
      if (!periodItemCount[period]) periodItemCount[period] = {};

      if (useJournals) {
        if (p.journal && topItems.includes(p.journal)) {
          periodItemCount[period][p.journal] = (periodItemCount[period][p.journal] || 0) + 1;
        }
      } else {
        p.keywords?.forEach((kw) => {
          const k = normalizeKw(kw, caseMap);
          if (topItems.includes(k)) periodItemCount[period][k] = (periodItemCount[period][k] || 0) + 1;
        });
      }
    });
  }

  const periods = Object.keys(periodItemCount).sort();

  // Compute ranks per period
  const items: { period: string; keyword: string; rank: number; count: number }[] = [];
  periods.forEach((period) => {
    const itemCounts = periodItemCount[period];
    const sorted = topItems
      .map((item) => ({ kw: item, count: itemCounts[item] || 0 }))
      .filter((d) => d.count > 0)
      .sort((a, b) => b.count - a.count);
    sorted.forEach((d, i) => {
      items.push({ period, keyword: d.kw, rank: i + 1, count: d.count });
    });
  });

  return { items, keywords: topItems, periods, dataType };
}

function processBubbleData(papers: Paper[], caseMap: Record<string, string>): BubbleData[] {
  const now = new Date();
  const halfYear = new Date(now.getTime() - 180 * 86400000);

  const kwTotal: Record<string, number> = {};
  const kwRecent: Record<string, number> = {};

  papers.forEach((p) => {
    const isRecent = p.created_at ? new Date(p.created_at) > halfYear : false;
    p.keywords?.forEach((kw) => {
      const k = normalizeKw(kw, caseMap);
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

function processNetworkData(papers: Paper[], caseMap: Record<string, string>) {
  const kwCounts: Record<string, number> = {};
  const edgeCounts: Record<string, number> = {};

  papers.forEach((p) => {
    const kws = (p.keywords || []).map((k) => normalizeKw(k, caseMap)).filter(Boolean);
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

function processDataQualityMetrics(papers: Paper[]): DataQualityMetric[] {
  const total = papers.length;
  if (total === 0) return [];

  // Calculate various data quality metrics
  const withKeywords = papers.filter(p => p.keywords && p.keywords.length > 0).length;
  const withAbstract = papers.filter(p => p.abstract && p.abstract.length > 50).length;
  const withMultipleAuthors = papers.filter(p => p.authors && p.authors.length > 1).length;
  const withAffiliation = papers.filter(p =>
    p.authors?.some(a => a.affiliation && a.affiliation.length > 10)
  ).length;
  const withOrcid = papers.filter(p =>
    p.authors?.some(a => a.orcid)
  ).length;
  const withCitations = papers.filter(p => p.citation_count && p.citation_count > 0).length;

  return [
    { axis: "Keywords", value: (withKeywords / total) * 100, count: withKeywords, total, description: "검색 및 분류에 사용되는 키워드 보유" },
    { axis: "Abstract", value: (withAbstract / total) * 100, count: withAbstract, total, description: "50자 이상의 초록 포함 여부" },
    { axis: "Co-Authors", value: (withMultipleAuthors / total) * 100, count: withMultipleAuthors, total, description: "2인 이상 공동 저자 연구" },
    { axis: "Affiliation", value: (withAffiliation / total) * 100, count: withAffiliation, total, description: "저자 소속 기관 정보 보유" },
    { axis: "ORCID", value: (withOrcid / total) * 100, count: withOrcid, total, description: "ORCID 식별자 보유 저자 포함" },
    { axis: "Citations", value: (withCitations / total) * 100, count: withCitations, total, description: "인용 횟수 데이터 보유" },
  ];
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

// Institution category classification
const INSTITUTION_CATEGORIES: { label: string; patterns: RegExp[] }[] = [
  { label: "Comprehensive University", patterns: [/university|universität|université|universidad|universidade|대학교/i] },
  { label: "Medical School / Hospital", patterns: [/medical school|hospital|clinic|charité|medical center|medical college|mayo|병원/i] },
  { label: "Engineering / Tech Institute", patterns: [/institute of technology|polytechnic|MIT\b|KAIST|Caltech|ETH|tech\b/i] },
  { label: "National Research Institute", patterns: [/national institute|national lab|NIH\b|CNRS|Max Planck|national center|국립/i] },
  { label: "Government / Public Agency", patterns: [/ministry|CDC\b|FDA\b|government|public health|WHO\b|agency/i] },
  { label: "Pharmaceutical / Biotech", patterns: [/pharma|biotech|pfizer|roche|novartis|merck|genentech|amgen|gilead|astrazeneca|johnson|bayer/i] },
  { label: "AI / Tech Company", patterns: [/google|deepmind|microsoft|meta ai|openai|nvidia|ibm research|amazon|apple|baidu|tencent|alibaba/i] },
  { label: "Academy of Sciences", patterns: [/academy of science|chinese academy|russian academy|académie|학술원/i] },
  { label: "Cancer / Specialized Center", patterns: [/cancer center|cancer institute|oncology|sloan|dana.farber|MD anderson/i] },
  { label: "Military / Defense", patterns: [/military|army|navy|defense|defence|air force|naval/i] },
  { label: "Private Research Foundation", patterns: [/foundation|howard hughes|wellcome|gates|salk|broad institute|cold spring|연구재단/i] },
  { label: "International Organization", patterns: [/WHO|UNESCO|IAEA|EMBL|CERN|world health|european molecular/i] },
  { label: "Children's / Pediatric", patterns: [/children|pediatric|paediatric|child health/i] },
  { label: "Veterinary / Agriculture", patterns: [/veterinary|agriculture|agricultural|agri\b|animal science/i] },
];

function classifyInstitution(affiliation: string): string {
  for (const cat of INSTITUTION_CATEGORIES) {
    for (const pat of cat.patterns) {
      if (pat.test(affiliation)) return cat.label;
    }
  }
  return "Other Research Org";
}

function processInstitutionTreemapData(papers: Paper[]) {
  const counts: Record<string, number> = {};
  papers.forEach((p) => {
    const seen = new Set<string>();
    p.authors?.forEach((a) => {
      if (!a.affiliation) return;
      const category = classifyInstitution(a.affiliation);
      if (!seen.has(category)) {
        seen.add(category);
        counts[category] = (counts[category] || 0) + 1;
      }
    });
  });
  const total = Object.values(counts).reduce((s, v) => s + v, 0) || 1;
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 15)
    .map(([name, value]) => ({ name, value, pct: (value / total) * 100 }));
}

// Extract country from affiliation text
const COUNTRY_PATTERNS: [RegExp, string][] = [
  [/\bUSA\b|\bUnited States\b|\bU\.S\.A/i, "USA"],
  [/\bUK\b|\bUnited Kingdom\b|\bEngland\b|\bScotland\b|\bWales\b|\bLondon\b/i, "UK"],
  [/\bChina\b|\bBeijing\b|\bShanghai\b|\bGuangzhou\b|\bXiamen\b/i, "China"],
  [/\bJapan\b|\bTokyo\b|\bOsaka\b/i, "Japan"],
  [/\bGermany\b|\bDeutschland\b|\bBerlin\b|\bMunich\b|\bDuisburg\b|\bEssen\b/i, "Germany"],
  [/\bFrance\b|\bParis\b/i, "France"],
  [/\bItaly\b|\bRoma\b|\bMilano\b/i, "Italy"],
  [/\bSpain\b|\bMadrid\b|\bBarcelona\b/i, "Spain"],
  [/\bCanada\b|\bToronto\b|\bVancouver\b/i, "Canada"],
  [/\bAustralia\b|\bMelbourne\b|\bSydney\b/i, "Australia"],
  [/\bSouth Korea\b|\bKorea\b|\bSeoul\b/i, "South Korea"],
  [/\bIndia\b|\bMumbai\b|\bDelhi\b/i, "India"],
  [/\bBrazil\b|\bSão Paulo\b/i, "Brazil"],
  [/\bNetherlands\b|\bAmsterdam\b/i, "Netherlands"],
  [/\bSwitzerland\b|\bZurich\b|\bGeneva\b|\bBasel\b/i, "Switzerland"],
  [/\bSweden\b|\bStockholm\b/i, "Sweden"],
  [/\bBelgium\b|\bLeuven\b|\bBrussels\b/i, "Belgium"],
  [/\bAustria\b|\bVienna\b/i, "Austria"],
  [/\bDenmark\b|\bCopenhagen\b/i, "Denmark"],
  [/\bNorway\b|\bOslo\b/i, "Norway"],
  [/\bFinland\b|\bHelsinki\b/i, "Finland"],
  [/\bPoland\b|\bWarsaw\b/i, "Poland"],
  [/\bTurkey\b|\bIstanbul\b|\bAnkara\b/i, "Turkey"],
  [/\bIsrael\b|\bTel Aviv\b/i, "Israel"],
  [/\bIran\b|\bTehran\b/i, "Iran"],
  [/\bTaiwan\b|\bTaipei\b/i, "Taiwan"],
  [/\bSingapore\b/i, "Singapore"],
  [/\bIreland\b|\bDublin\b/i, "Ireland"],
  [/\bPortugal\b|\bLisbon\b/i, "Portugal"],
  [/\bGreece\b|\bAthens\b/i, "Greece"],
];

function extractCountry(affiliation: string): string | null {
  for (const [regex, country] of COUNTRY_PATTERNS) {
    if (regex.test(affiliation)) return country;
  }
  return null;
}

function processWorldMapData(papers: Paper[]): CountryData[] {
  const countryCounts: Record<string, number> = {};
  papers.forEach((p) => {
    const seen = new Set<string>();
    p.authors?.forEach((a) => {
      if (!a.affiliation) return;
      const country = extractCountry(a.affiliation);
      if (country && !seen.has(country)) {
        seen.add(country);
        countryCounts[country] = (countryCounts[country] || 0) + 1;
      }
    });
  });

  return Object.entries(countryCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 25)
    .filter(([country]) => COUNTRY_COORDS[country])
    .map(([country, count]) => ({
      country,
      count,
      lat: COUNTRY_COORDS[country][1],
      lng: COUNTRY_COORDS[country][0],
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
  const [selectedKeyword, setSelectedKeyword] = useState<string | null>(null);
  const [useMockData, setUseMockData] = useState(false);

  // Data queries
  const statsQuery = useQuery({
    queryKey: ["dashboard", "stats"],
    queryFn: dashboardApi.getPaperStats,
    enabled: !useMockData,
  });

  const papersQuery = useQuery({
    queryKey: ["dashboard", "analysisPapers"],
    queryFn: () => dashboardApi.getAnalysisPapers(500),  // API limit is 500
    enabled: !useMockData,
    staleTime: 5 * 60 * 1000,  // Cache for 5 minutes
  });

  const papers = useMockData ? getMockPapers() : (papersQuery.data || []);

  // Case-insensitive keyword map
  const caseMap = useMemo(() => buildCaseMap(papers), [papers]);

  // Processed data
  const bumpData = useMemo(() => processBumpData(papers, caseMap), [papers, caseMap]);
  const bubbleData = useMemo(() => processBubbleData(papers, caseMap), [papers, caseMap]);
  const networkData = useMemo(() => processNetworkData(papers, caseMap), [papers, caseMap]);
  const heatmapData = useMemo(() => processHeatmapData(papers), [papers]);
  const dataQualityMetrics = useMemo(() => processDataQualityMetrics(papers), [papers]);
  const topJournals = useMemo(() => processTopJournals(papers), [papers]);
  const topAuthors = useMemo(() => processTopAuthors(papers), [papers]);
  const institutionTreemapData = useMemo(() => processInstitutionTreemapData(papers), [papers]);
  const worldMapData = useMemo(() => processWorldMapData(papers), [papers]);
  const statsData = useMockData ? MOCK_STATS : statsQuery.data;
  const radialData = useMemo(() => {
    if (!statsData?.by_year && papers.length === 0) return [];

    // Gather year counts from stats or papers
    const byYear = statsData?.by_year
      ? [...statsData.by_year].sort((a, b) => a.year - b.year)
      : [];
    const yearsWithData = byYear.filter((d) => d.count > 0);

    // If ≤3 distinct years → use monthly breakdown from papers for granularity
    if (yearsWithData.length <= 3 && papers.length > 0) {
      const mCounts: Record<string, number> = {};
      papers.forEach((p) => {
        if (!p.created_at) return;
        const d = new Date(p.created_at);
        const yr = String(d.getFullYear()).slice(2);
        const mo = d.getMonth() + 1;
        const label = `${yr}.${String(mo).padStart(2, "0")}`;
        const sortKey = d.getFullYear() * 100 + mo;
        mCounts[`${sortKey}|${label}`] = (mCounts[`${sortKey}|${label}`] || 0) + 1;
      });
      return Object.entries(mCounts)
        .sort(([a], [b]) => parseInt(a) - parseInt(b))
        .map(([key, count]) => ({
          year: parseInt(key.split("|")[0]),
          count,
          label: key.split("|")[1],
        }));
    }

    return byYear.map((d) => ({ ...d, label: undefined }));
  }, [statsData, papers]);

  // Derived stats
  const totalPapers = statsData?.total || 0;
  const recentCount = statsData?.recent_count || 0;
  const uniqueKeywords = useMemo(() => {
    const set = new Set<string>();
    papers.forEach((p) => p.keywords?.forEach((k) => set.add(normalizeKw(k, caseMap).toLowerCase())));
    return set.size;
  }, [papers, caseMap]);
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


  const isLoading = !useMockData && (statsQuery.isLoading || papersQuery.isLoading);

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
          {/* Title + Data Source Toggle */}
          <div className="mb-8 flex items-start justify-between">
            <div>
              <h1 className="font-[family-name:var(--font-outfit)] text-3xl font-semibold mb-1">
                Dashboard
              </h1>
              <p className="font-[family-name:var(--font-dm-sans)] text-base text-[var(--oaria-text-secondary)]">
                논문 데이터 분석 및 인사이트
              </p>
            </div>
            <button
              onClick={() => setUseMockData((v) => !v)}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl border text-sm font-medium transition-all ${
                useMockData
                  ? "border-[var(--oaria-teal)] bg-[var(--oaria-teal)]/10 text-[var(--oaria-teal)]"
                  : "border-[var(--oaria-border)] text-[var(--oaria-text-secondary)] hover:border-[var(--oaria-teal)] hover:text-[var(--oaria-teal)]"
              }`}
            >
              {useMockData ? <FlaskConical size={16} /> : <Database size={16} />}
              {useMockData ? "Mock Data" : "Live Data"}
            </button>
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

              {/* ─── Row 2: Keyword/Journal Ranking (full width) ─── */}
              <ChartSection
                title={(bumpData as { dataType?: string }).dataType === "journal" ? "Journal Trends" : "Keyword Ranking"}
                subtitle={(bumpData as { dataType?: string }).dataType === "journal"
                  ? "기간별 주요 저널 순위 변화 (Bump Chart)"
                  : "기간별 핵심 키워드 순위 변화 (Bump Chart)"}
                className="mb-6"
              >
                <div className="h-80">
                  <BumpChart
                    data={bumpData.items}
                    keywords={bumpData.keywords}
                    periods={bumpData.periods}
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
                    subtitle="논문 수 기준 상위 저널"
                  >
                    <div className="h-56">
                      <JournalLollipop data={topJournals} />
                    </div>
                  </ChartSection>

                  <ChartSection
                    title="Data Quality"
                    subtitle="논문 메타데이터 품질 지표"
                  >
                    <div className="h-56">
                      <DataQualityRadar
                        data={dataQualityMetrics}
                        totalPapers={totalPapers}
                        sampleSize={papers.length}
                      />
                    </div>
                  </ChartSection>
                </div>
              </div>

              {/* ─── Row 5: Institution Treemap (full width, BTC style) ─── */}
              <ChartSection
                title="Institution Categories"
                subtitle="연구 기관 유형별 논문 비중"
                className="mb-6"
              >
                <div className="h-80">
                  <JournalTreemap data={institutionTreemapData} />
                </div>
              </ChartSection>

              {/* ─── Row 6: World Map (full width, taller) ─── */}
              <ChartSection
                title="Global Research Map"
                subtitle="저자 소속 기관 국가별 분포"
                className="mb-6"
              >
                <div className="h-[480px]">
                  <WorldMap data={worldMapData} />
                </div>
              </ChartSection>

              {/* ─── Row 7: Radial + Authors ─── */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                <ChartSection
                  title="Year Distribution"
                  subtitle={radialData.some((d) => d.label) ? "월별 논문 분포 (Radial)" : "연도별 논문 분포 (Radial)"}
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

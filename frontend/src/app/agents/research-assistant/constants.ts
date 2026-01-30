// ─────────────────────────────────────────────────────────────
// Research Assistant - Constants
// Vector-Based 3D Reasoning Engine
// ─────────────────────────────────────────────────────────────

import type { GraphNode, GraphLink, ClusterConfig } from "./types";

// Node 타입별 색상
export const NODE_COLORS: Record<string, string> = {
  paper: "#3498db",
  author: "#2ecc71",
  keyword: "#f39c12",
  concept: "#9b59b6",
};

// Link 타입별 색상
export const LINK_COLORS: Record<string, string> = {
  similar: "#7f8c8d",
  authored: "#27ae60",
  contains: "#e67e22",
  causal: "#e74c3c",
  correlational: "#3498db",
  hierarchical: "#9b59b6",
  contradictory: "#c0392b",
};

// 클러스터 설정
export const CLUSTER_COLORS: Record<string, ClusterConfig> = {
  combo: { color: "#3498db", label: "Combination IO" },
  novel_target: { color: "#9b59b6", label: "Novel Targets" },
  biomarker: { color: "#e67e22", label: "Biomarker-Driven" },
  safety: { color: "#e74c3c", label: "Safety Profile" },
  mechanism: { color: "#1abc9c", label: "Mechanism" },
  clinical: { color: "#2980b9", label: "Clinical Trial" },
};

// Link 타입 라벨
export const LINK_LABELS: Record<string, string> = {
  similar: "Similar",
  authored: "Author",
  contains: "Keyword",
  causal: "Causal",
  correlational: "Correlation",
  hierarchical: "Hierarchy",
  contradictory: "Contradicts",
};

// 샘플 데이터 생성
export function generateSampleGraphData(): { nodes: GraphNode[]; links: GraphLink[] } {
  const papers: GraphNode[] = [
    {
      id: "p1",
      type: "paper",
      label: "Durvalumab + Tremelimumab + Chemo in NSCLC",
      cluster: "combo",
      metadata: {
        pmid: "38012345",
        journal: "Nature Medicine",
        pubdate: "2024 Jan",
        abstract:
          "In this randomized, open-label, phase 3 trial, we assigned patients with metastatic non-small-cell lung cancer (NSCLC) to receive tremelimumab plus durvalumab and chemotherapy...",
        certainty_score: 0.92,
      },
    },
    {
      id: "p2",
      type: "paper",
      label: "Pembrolizumab + Chemo in Metastatic NSCLC",
      cluster: "combo",
      metadata: {
        pmid: "37098765",
        journal: "NEJM",
        pubdate: "2023 Sep",
        abstract:
          "Pembrolizumab combined with chemotherapy significantly improved overall survival in patients with previously untreated metastatic non-small-cell lung cancer without EGFR or ALK mutations...",
        certainty_score: 0.95,
      },
    },
    {
      id: "p3",
      type: "paper",
      label: "Nivolumab + Ipilimumab in Advanced NSCLC",
      cluster: "combo",
      metadata: {
        pmid: "36054321",
        journal: "Lancet Oncology",
        pubdate: "2023 Mar",
        abstract:
          "First-line nivolumab plus ipilimumab combined with two cycles of chemotherapy provided durable clinical benefit versus chemotherapy alone...",
        certainty_score: 0.89,
      },
    },
    {
      id: "p4",
      type: "paper",
      label: "Atezolizumab First-Line Metastatic NSCLC",
      cluster: "combo",
      metadata: {
        pmid: "35067890",
        journal: "J Clin Oncol",
        pubdate: "2022 Nov",
        abstract:
          "Atezolizumab in combination with bevacizumab, carboplatin, and paclitaxel significantly improved PFS and OS in metastatic non-squamous NSCLC...",
        certainty_score: 0.87,
      },
    },
    {
      id: "p5",
      type: "paper",
      label: "TIGIT + PD-L1 Blockade Phase 2 Results",
      cluster: "novel_target",
      metadata: {
        pmid: "39001234",
        journal: "Nature",
        pubdate: "2024 Jun",
        abstract:
          "Co-blockade of TIGIT and PD-L1 showed a 24% higher objective response rate compared to PD-L1 monotherapy in PD-L1-high NSCLC patients...",
        certainty_score: 0.85,
      },
    },
    {
      id: "p6",
      type: "paper",
      label: "ctDNA-guided Immunotherapy in Stage III NSCLC",
      cluster: "biomarker",
      metadata: {
        pmid: "39112233",
        journal: "Ann Oncol",
        pubdate: "2024 Apr",
        abstract:
          "Circulating tumor DNA-guided adaptive immunotherapy demonstrated feasibility in post-chemoradiation stage III NSCLC...",
        certainty_score: 0.78,
      },
    },
    {
      id: "p7",
      type: "paper",
      label: "Biomarker-Driven Neoadjuvant IO Combinations",
      cluster: "biomarker",
      metadata: {
        pmid: "38223344",
        journal: "Lancet",
        pubdate: "2024 Feb",
        abstract:
          "Biomarker-stratified neoadjuvant immunotherapy combinations show differential pathological complete response rates across PD-L1 expression levels...",
        certainty_score: 0.82,
      },
    },
    {
      id: "p8",
      type: "paper",
      label: "Elderly Population Immunotherapy Safety Profile",
      cluster: "safety",
      metadata: {
        pmid: "37334455",
        journal: "JAMA Oncol",
        pubdate: "2023 Aug",
        abstract:
          "Immunotherapy safety and efficacy in patients aged 75+ remains underrepresented. This meta-analysis pooled data from 12 trials...",
        certainty_score: 0.75,
      },
    },
  ];

  const authors: GraphNode[] = [
    { id: "a1", type: "author", label: "Dr. Rizvi, N.", metadata: { paper_count: 142 } },
    { id: "a2", type: "author", label: "Prof. Peters, S.", metadata: { paper_count: 118 } },
    { id: "a3", type: "author", label: "Dr. Garon, E.", metadata: { paper_count: 96 } },
    { id: "a4", type: "author", label: "Dr. Paz-Ares, L.", metadata: { paper_count: 89 } },
    { id: "a5", type: "author", label: "Dr. Herbst, R.", metadata: { paper_count: 134 } },
    { id: "a6", type: "author", label: "Prof. Reck, M.", metadata: { paper_count: 105 } },
  ];

  const keywords: GraphNode[] = [
    { id: "k1", type: "keyword", label: "Immunotherapy" },
    { id: "k2", type: "keyword", label: "PD-L1" },
    { id: "k3", type: "keyword", label: "NSCLC" },
    { id: "k4", type: "keyword", label: "Biomarkers" },
    { id: "k5", type: "keyword", label: "Survival Rate" },
    { id: "k6", type: "keyword", label: "Chemotherapy" },
    { id: "k7", type: "keyword", label: "TIGIT" },
    { id: "k8", type: "keyword", label: "ctDNA" },
    { id: "k9", type: "keyword", label: "Toxicity" },
    { id: "k10", type: "keyword", label: "Resistance" },
  ];

  const nodes = [...papers, ...authors, ...keywords];

  const links: GraphLink[] = [
    // Paper-Paper (similar)
    { source: "p1", target: "p2", similarity: 0.88, type: "similar" },
    { source: "p1", target: "p3", similarity: 0.82, type: "similar" },
    { source: "p2", target: "p4", similarity: 0.79, type: "similar" },
    { source: "p3", target: "p4", similarity: 0.75, type: "similar" },
    { source: "p5", target: "p1", similarity: 0.72, type: "similar" },
    { source: "p5", target: "p7", similarity: 0.85, type: "similar" },
    { source: "p6", target: "p7", similarity: 0.78, type: "similar" },
    { source: "p6", target: "p8", similarity: 0.71, type: "similar" },
    { source: "p2", target: "p8", similarity: 0.68, type: "similar" },
    { source: "p3", target: "p5", similarity: 0.74, type: "similar" },
    // Author-Paper (authored)
    { source: "a1", target: "p1", similarity: 1, type: "authored" },
    { source: "a1", target: "p5", similarity: 1, type: "authored" },
    { source: "a2", target: "p2", similarity: 1, type: "authored" },
    { source: "a2", target: "p7", similarity: 1, type: "authored" },
    { source: "a3", target: "p3", similarity: 1, type: "authored" },
    { source: "a4", target: "p4", similarity: 1, type: "authored" },
    { source: "a4", target: "p1", similarity: 1, type: "authored" },
    { source: "a5", target: "p5", similarity: 1, type: "authored" },
    { source: "a5", target: "p6", similarity: 1, type: "authored" },
    { source: "a6", target: "p8", similarity: 1, type: "authored" },
    { source: "a6", target: "p3", similarity: 1, type: "authored" },
    // Paper-Keyword (contains)
    { source: "p1", target: "k1", similarity: 1, type: "contains" },
    { source: "p1", target: "k3", similarity: 1, type: "contains" },
    { source: "p1", target: "k6", similarity: 1, type: "contains" },
    { source: "p2", target: "k1", similarity: 1, type: "contains" },
    { source: "p2", target: "k2", similarity: 1, type: "contains" },
    { source: "p2", target: "k3", similarity: 1, type: "contains" },
    { source: "p3", target: "k1", similarity: 1, type: "contains" },
    { source: "p3", target: "k5", similarity: 1, type: "contains" },
    { source: "p4", target: "k3", similarity: 1, type: "contains" },
    { source: "p4", target: "k4", similarity: 1, type: "contains" },
    { source: "p5", target: "k7", similarity: 1, type: "contains" },
    { source: "p5", target: "k2", similarity: 1, type: "contains" },
    { source: "p6", target: "k8", similarity: 1, type: "contains" },
    { source: "p6", target: "k1", similarity: 1, type: "contains" },
    { source: "p7", target: "k4", similarity: 1, type: "contains" },
    { source: "p7", target: "k1", similarity: 1, type: "contains" },
    { source: "p8", target: "k9", similarity: 1, type: "contains" },
    { source: "p8", target: "k10", similarity: 1, type: "contains" },
    { source: "p8", target: "k5", similarity: 1, type: "contains" },
  ];

  return { nodes, links };
}

// 예시 질문들
export const EXAMPLE_QUESTIONS = [
  {
    category: "논문 분석",
    questions: [
      "EGFR 변이 비소세포폐암의 최신 표적치료제 연구 동향을 분석해주세요.",
      "면역관문억제제의 병용요법 효과에 대한 최근 임상연구를 요약해주세요.",
    ],
  },
  {
    category: "연구 동향",
    questions: [
      "삼중음성유방암에서 PARP 억제제와 면역항암제의 치료 효과를 비교해 주세요.",
      "정밀의료 기반 암 진단의 최신 기술 발전을 알려주세요.",
    ],
  },
  {
    category: "문헌 고찰",
    questions: [
      "PD-1/PD-L1 억제제의 바이오마커 연구에 대해 분석해주세요.",
      "KRAS G12C 변이 표적치료제의 임상 데이터를 종합해주세요.",
    ],
  },
];

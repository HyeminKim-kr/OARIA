import axios from "axios";
import type { VectorGraphResponse, VectorSearchRequest, GraphNode, GraphLink } from "./types";

// API URL - 기존 OARIA 백엔드 서버
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// 토큰 인터셉터 (iframe에서 postMessage로 받은 토큰 사용)
let accessToken: string | null = null;

export function setAccessToken(token: string) {
  accessToken = token;
}

api.interceptors.request.use(
  (config) => {
    if (accessToken) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Research Assistant API
export const researchAssistantApi = {
  searchVectorGraph: (request: VectorSearchRequest) =>
    api.post<VectorGraphResponse>('/ai/research/vector-graph', request)
      .then((res) => res.data),
};

// 샘플 데이터 생성 (API 연결 전 테스트용)
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
        certainty_score: 0.89,
      },
    },
    {
      id: "p4",
      type: "paper",
      label: "Atezolizumab First-Line Metastatic NSCLC",
      cluster: "combo",
      metadata: { journal: "J Clin Oncol", certainty_score: 0.87 },
    },
    {
      id: "p5",
      type: "paper",
      label: "TIGIT + PD-L1 Blockade Phase 2 Results",
      cluster: "novel_target",
      metadata: { journal: "Nature", certainty_score: 0.85 },
    },
    {
      id: "p6",
      type: "paper",
      label: "ctDNA-guided Immunotherapy in Stage III NSCLC",
      cluster: "biomarker",
      metadata: { journal: "Ann Oncol", certainty_score: 0.78 },
    },
    {
      id: "p7",
      type: "paper",
      label: "Biomarker-Driven Neoadjuvant IO Combinations",
      cluster: "biomarker",
      metadata: { journal: "Lancet", certainty_score: 0.82 },
    },
    {
      id: "p8",
      type: "paper",
      label: "Elderly Population Immunotherapy Safety Profile",
      cluster: "safety",
      metadata: { journal: "JAMA Oncol", certainty_score: 0.75 },
    },
  ];

  const authors: GraphNode[] = [
    { id: "a1", type: "author", label: "Dr. Rizvi, N.", metadata: { paper_count: 142 } },
    { id: "a2", type: "author", label: "Prof. Peters, S.", metadata: { paper_count: 118 } },
    { id: "a3", type: "author", label: "Dr. Garon, E.", metadata: { paper_count: 96 } },
    { id: "a4", type: "author", label: "Dr. Paz-Ares, L.", metadata: { paper_count: 89 } },
    { id: "a5", type: "author", label: "Dr. Herbst, R.", metadata: { paper_count: 134 } },
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
  ];

  const nodes = [...papers, ...authors, ...keywords];

  const links: GraphLink[] = [
    { source: "p1", target: "p2", similarity: 0.88, type: "similar" },
    { source: "p1", target: "p3", similarity: 0.82, type: "similar" },
    { source: "p2", target: "p4", similarity: 0.79, type: "similar" },
    { source: "p3", target: "p4", similarity: 0.75, type: "similar" },
    { source: "p5", target: "p1", similarity: 0.72, type: "similar" },
    { source: "p5", target: "p7", similarity: 0.85, type: "similar" },
    { source: "p6", target: "p7", similarity: 0.78, type: "similar" },
    { source: "p6", target: "p8", similarity: 0.71, type: "similar" },
    { source: "a1", target: "p1", similarity: 1, type: "authored" },
    { source: "a1", target: "p5", similarity: 1, type: "authored" },
    { source: "a2", target: "p2", similarity: 1, type: "authored" },
    { source: "a3", target: "p3", similarity: 1, type: "authored" },
    { source: "a4", target: "p4", similarity: 1, type: "authored" },
    { source: "a5", target: "p5", similarity: 1, type: "authored" },
    { source: "p1", target: "k1", similarity: 1, type: "contains" },
    { source: "p1", target: "k3", similarity: 1, type: "contains" },
    { source: "p2", target: "k1", similarity: 1, type: "contains" },
    { source: "p2", target: "k2", similarity: 1, type: "contains" },
    { source: "p5", target: "k7", similarity: 1, type: "contains" },
    { source: "p6", target: "k8", similarity: 1, type: "contains" },
    { source: "p7", target: "k4", similarity: 1, type: "contains" },
  ];

  return { nodes, links };
}

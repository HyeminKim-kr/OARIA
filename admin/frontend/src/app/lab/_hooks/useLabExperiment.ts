import { useState, useCallback, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { labApi, ragSettingsApi, sampleEmbeddingsApi } from '@/lib/api';
import { TestMode, CompareResults, LabConfig, FeedbackState, SearchConfig, DataSource } from '../_lib';
import { DEFAULT_CONFIG } from '../_lib';

export function useLabExperiment() {
  const [mode, setMode] = useState<TestMode>('search');
  const [config, setConfig] = useState<LabConfig>(DEFAULT_CONFIG);
  const [compareResults, setCompareResults] = useState<CompareResults>({});
  const [feedbackSubmitted, setFeedbackSubmitted] = useState<FeedbackState>({});

  // User Backend 상태 확인
  const { data: status } = useQuery({
    queryKey: ['lab', 'status'],
    queryFn: () => labApi.getStatus(),
    refetchInterval: 30000,
  });

  // RAG 전략 목록 조회 (이름만)
  const { data: strategies } = useQuery({
    queryKey: ['lab', 'strategies'],
    queryFn: () => labApi.getStrategies(),
    staleTime: 5 * 60 * 1000, // 5분간 캐시
  });

  // RAG 전략 상세 정보 조회 (설명 포함)
  const { data: strategiesDetail } = useQuery({
    queryKey: ['lab', 'strategies', 'detail'],
    queryFn: () => labApi.getStrategiesDetail(),
    staleTime: 5 * 60 * 1000,
  });

  // 활성 RAG 설정 조회
  const { data: activeSettings } = useQuery({
    queryKey: ['rag-settings', 'active'],
    queryFn: () => ragSettingsApi.getActive(),
    staleTime: 5 * 60 * 1000,
  });

  // 완료된 샘플 임베딩 목록 조회 (데이터 소스 선택용)
  const { data: sampleEmbeddings } = useQuery({
    queryKey: ['sample-embeddings', 'completed'],
    queryFn: () => sampleEmbeddingsApi.getAll({ status: 'completed' }),
    staleTime: 60 * 1000, // 1분간 캐시
  });

  // 활성 설정이 로드되면 selectedStrategies 초기화
  useEffect(() => {
    if (activeSettings) {
      setConfig((prev) => ({
        ...prev,
        selectedStrategies: {
          chunker: activeSettings.chunker,
          embedder: activeSettings.embedder,
          retriever: activeSettings.retriever,
          reranker: activeSettings.reranker || 'none',
          classifier: prev.selectedStrategies.classifier,  // classifier는 기존값 유지
        },
        // 기본 검색 설정도 활성 설정 기반으로
        limit: activeSettings.parameters?.limit ?? prev.limit,
        alpha: activeSettings.parameters?.alpha ?? prev.alpha,
        reranker: activeSettings.reranker || 'bge',
        useReranker: !!activeSettings.reranker,
      }));
    }
  }, [activeSettings]);

  // 검색 테스트
  const searchMutation = useMutation({
    mutationFn: () =>
      labApi.testSearch({
        query: config.query,
        limit: config.limit,
        alpha: config.alpha,
        useReranker: config.useReranker,
        reranker: config.useReranker ? config.reranker : undefined,
        collectionName: config.dataSource === 'sample' && config.collectionName ? config.collectionName : undefined,
        classifier: config.selectedStrategies.classifier !== 'none' ? config.selectedStrategies.classifier : undefined,
      }),
  });

  // 답변 생성 테스트
  const generateMutation = useMutation({
    mutationFn: () =>
      labApi.testGenerate({
        query: config.query,
        limit: config.limit,
        alpha: config.alpha,
        useReranker: config.useReranker,
        reranker: config.useReranker ? config.reranker : undefined,
        collectionName: config.dataSource === 'sample' && config.collectionName ? config.collectionName : undefined,
        classifier: config.selectedStrategies.classifier !== 'none' ? config.selectedStrategies.classifier : undefined,
      }),
  });

  // A/B 비교 테스트
  const compareMutation = useMutation({
    mutationFn: () =>
      labApi.testCompare({
        query: config.query,
        configA: config.configA,
        configB: config.configB,
      }),
    onSuccess: (data) => {
      setCompareResults({
        configA: data.configA,
        configB: data.configB,
      });
    },
  });

  // A/B 설정 업데이트 헬퍼
  const updateConfigA = useCallback((updates: Partial<SearchConfig>) => {
    setConfig((prev) => ({
      ...prev,
      configA: { ...prev.configA, ...updates },
    }));
  }, []);

  const updateConfigB = useCallback((updates: Partial<SearchConfig>) => {
    setConfig((prev) => ({
      ...prev,
      configB: { ...prev.configB, ...updates },
    }));
  }, []);

  // 전략 선택 업데이트
  const updateStrategy = useCallback((key: string, value: string) => {
    setConfig((prev) => ({
      ...prev,
      selectedStrategies: { ...prev.selectedStrategies, [key]: value },
    }));
  }, []);

  // 데이터 소스 업데이트
  const updateDataSource = useCallback((dataSource: DataSource, collectionName: string | null) => {
    setConfig((prev) => ({
      ...prev,
      dataSource,
      collectionName,
    }));
  }, []);

  const handleTest = useCallback(() => {
    if (!config.query.trim()) return;

    setFeedbackSubmitted({});

    if (mode === 'search') {
      searchMutation.mutate();
    } else if (mode === 'generate') {
      generateMutation.mutate();
    } else if (mode === 'compare') {
      setCompareResults({});
      compareMutation.mutate();
    }
  }, [mode, config, searchMutation, generateMutation, compareMutation]);

  const updateConfig = useCallback((updates: Partial<LabConfig>) => {
    setConfig((prev) => ({ ...prev, ...updates }));
  }, []);

  const isLoading =
    searchMutation.isPending || generateMutation.isPending || compareMutation.isPending;

  const error = searchMutation.error || generateMutation.error || compareMutation.error;

  return {
    mode,
    setMode,
    config,
    updateConfig,
    updateConfigA,
    updateConfigB,
    updateStrategy,
    updateDataSource,
    status,
    strategies,
    strategiesDetail, // 전략 상세 정보 (설명 포함)
    activeSettings, // 현재 활성 RAG 설정
    sampleEmbeddings, // 완료된 샘플 임베딩 목록
    isLoading,
    error,
    handleTest,
    searchResult: searchMutation.data,
    generateResult: generateMutation.data,
    compareResults,
    feedbackSubmitted,
    setFeedbackSubmitted,
  };
}

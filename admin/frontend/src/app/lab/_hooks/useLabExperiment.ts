import { useState, useCallback, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { labApi, ragSettingsApi, sampleEmbeddingsApi } from '@/lib/api';
import { TestMode, CompareResults, LabConfig, FeedbackState, SearchConfig, DataSourceConfig, SearchSettings } from '../_lib';
import { DEFAULT_CONFIG, DEFAULT_PRODUCTION_DATA_SOURCE, DEFAULT_SEARCH_SETTINGS } from '../_lib';

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

  // 활성 설정이 로드되면 초기화
  useEffect(() => {
    if (activeSettings) {
      const newSearchSettings: SearchSettings = {
        retriever: activeSettings.retriever,
        reranker: activeSettings.reranker || 'none',
        classifier: activeSettings.classifier || 'none',
      };

      const newDataSource: DataSourceConfig = {
        type: 'production',
        collectionName: null,
        chunker: activeSettings.chunker,
        embedder: activeSettings.embedder,
      };

      setConfig((prev) => ({
        ...prev,
        // 새 구조
        searchSettings: newSearchSettings,
        dataSource: newDataSource,
        // 검색 파라미터
        limit: activeSettings.parameters?.limit ?? prev.limit,
        alpha: activeSettings.parameters?.alpha ?? prev.alpha,
        // 레거시 호환용
        selectedStrategies: {
          chunker: activeSettings.chunker,
          embedder: activeSettings.embedder,
          retriever: activeSettings.retriever,
          reranker: activeSettings.reranker || 'none',
          classifier: activeSettings.classifier || 'none',
        },
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
        useReranker: config.searchSettings.reranker !== 'none',
        reranker: config.searchSettings.reranker !== 'none' ? config.searchSettings.reranker : undefined,
        collectionName: config.dataSource.type === 'sample' ? config.dataSource.collectionName ?? undefined : undefined,
        classifier: config.searchSettings.classifier !== 'none' ? config.searchSettings.classifier : undefined,
      }),
  });

  // 답변 생성 테스트
  const generateMutation = useMutation({
    mutationFn: () =>
      labApi.testGenerate({
        query: config.query,
        limit: config.limit,
        alpha: config.alpha,
        useReranker: config.searchSettings.reranker !== 'none',
        reranker: config.searchSettings.reranker !== 'none' ? config.searchSettings.reranker : undefined,
        collectionName: config.dataSource.type === 'sample' ? config.dataSource.collectionName ?? undefined : undefined,
        classifier: config.searchSettings.classifier !== 'none' ? config.searchSettings.classifier : undefined,
      }),
  });

  // A/B 비교 테스트
  const compareMutation = useMutation({
    mutationFn: () => {
      // 새 SearchConfig를 API의 CompareSearchConfig 형식으로 변환
      const toApiConfig = (cfg: SearchConfig) => ({
        limit: cfg.limit,
        alpha: cfg.alpha,
        reranker: config.searchSettings.reranker !== 'none' ? config.searchSettings.reranker : null,
        collectionName: cfg.dataSource.type === 'sample' ? cfg.dataSource.collectionName : null,
      });

      return labApi.testCompare({
        query: config.query,
        configA: toApiConfig(config.configA),
        configB: toApiConfig(config.configB),
      });
    },
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

  // 검색 설정 업데이트 (Retriever, Reranker, Classifier)
  const updateSearchSettings = useCallback((settings: SearchSettings) => {
    setConfig((prev) => ({
      ...prev,
      searchSettings: settings,
      // 레거시 호환용
      selectedStrategies: {
        ...prev.selectedStrategies,
        retriever: settings.retriever,
        reranker: settings.reranker,
        classifier: settings.classifier,
      },
      useReranker: settings.reranker !== 'none',
      reranker: settings.reranker !== 'none' ? settings.reranker : prev.reranker,
    }));
  }, []);

  // 전략 선택 업데이트 (레거시 호환용)
  const updateStrategy = useCallback((key: string, value: string) => {
    setConfig((prev) => ({
      ...prev,
      selectedStrategies: { ...prev.selectedStrategies, [key]: value },
      // 검색 설정에도 반영
      searchSettings: ['retriever', 'reranker', 'classifier'].includes(key)
        ? { ...prev.searchSettings, [key]: value }
        : prev.searchSettings,
    }));
  }, []);

  // 데이터 소스 업데이트
  const updateDataSource = useCallback((dataSource: DataSourceConfig) => {
    setConfig((prev) => ({
      ...prev,
      dataSource,
      // 레거시 호환용
      collectionName: dataSource.collectionName,
      selectedStrategies: {
        ...prev.selectedStrategies,
        chunker: dataSource.chunker,
        embedder: dataSource.embedder,
      },
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
    updateSearchSettings,  // 새 검색 설정 업데이트 함수
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

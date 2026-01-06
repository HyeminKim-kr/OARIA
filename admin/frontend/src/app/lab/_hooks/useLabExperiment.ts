import { useState, useCallback } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { labApi } from '@/lib/api';
import { TestMode, CompareResults, LabConfig, FeedbackState } from '../_lib';
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

  // 검색 테스트
  const searchMutation = useMutation({
    mutationFn: () =>
      labApi.testSearch({
        query: config.query,
        limit: config.limit,
        alpha: config.alpha,
        useReranker: config.useReranker,
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
      }),
  });

  // A/B 비교 테스트
  const compareMutation = useMutation({
    mutationFn: () =>
      labApi.testCompare({
        query: config.query,
        limit: config.limit,
        alpha: config.alpha,
      }),
    onSuccess: (data) => {
      setCompareResults({
        withReranker: data.withReranker,
        withoutReranker: data.withoutReranker,
      });
    },
  });

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
    status,
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

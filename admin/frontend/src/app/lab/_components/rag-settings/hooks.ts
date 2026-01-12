'use client';

import { useMemo, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ragSettingsApi, labApi, RAGSettings, StrategiesResponse } from '@/lib/api';
import { StrategyOptions, SettingMismatch, StrategyType } from './types';
import { isValidStrategy } from './utils';

/**
 * RAG 전략 목록 조회 훅
 */
export function useStrategies(initialData?: StrategiesResponse) {
  return useQuery({
    queryKey: ['lab-strategies'],
    queryFn: labApi.getStrategies,
    initialData,
    staleTime: 1000 * 60 * 5, // 5분간 캐시
  });
}

/**
 * RAG 설정 목록 조회 훅
 */
export function useRAGSettings() {
  return useQuery({
    queryKey: ['rag-settings'],
    queryFn: ragSettingsApi.getAll,
  });
}

/**
 * RAG 설정 관련 뮤테이션 훅들
 */
export function useRAGSettingsMutations() {
  const queryClient = useQueryClient();

  const activateMutation = useMutation({
    mutationFn: ragSettingsApi.activate,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rag-settings'] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: {
        name?: string;
        description?: string;
        chunker?: string;
        embedder?: string;
        retriever?: string;
        reranker?: string | null;
        classifier?: string | null;
      };
    }) =>
      ragSettingsApi.update(id, {
        ...data,
        description: data.description ?? undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rag-settings'] });
    },
  });

  const createMutation = useMutation({
    mutationFn: ragSettingsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rag-settings'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: ragSettingsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rag-settings'] });
    },
  });

  return {
    activateMutation,
    updateMutation,
    createMutation,
    deleteMutation,
  };
}

/**
 * 전략 옵션을 가공하는 훅
 */
export function useStrategyOptions(strategies: StrategiesResponse | undefined): StrategyOptions {
  const chunkers = useMemo(() => strategies?.chunkers ?? [], [strategies?.chunkers]);
  const embedders = useMemo(() => strategies?.embedders ?? [], [strategies?.embedders]);
  const retrievers = useMemo(() => strategies?.retrievers ?? [], [strategies?.retrievers]);

  const rerankers = useMemo(() => {
    const filtered = strategies?.rerankers?.filter((r) => r !== 'none') ?? [];
    return ['none', ...filtered];
  }, [strategies?.rerankers]);

  const classifiers = useMemo(() => {
    const filtered = strategies?.classifiers?.filter((c) => c !== 'none') ?? [];
    return ['none', ...filtered];
  }, [strategies?.classifiers]);

  return { chunkers, embedders, retrievers, rerankers, classifiers };
}

/**
 * 설정 불일치 감지 훅
 */
export function useSettingMismatches(options: StrategyOptions) {
  return useCallback(
    (setting: RAGSettings): SettingMismatch[] => {
      const mismatches: SettingMismatch[] = [];

      const checks: { type: StrategyType; value: string | null; options: string[] }[] = [
        { type: 'chunker', value: setting.chunker, options: options.chunkers },
        { type: 'embedder', value: setting.embedder, options: options.embedders },
        { type: 'retriever', value: setting.retriever, options: options.retrievers },
        { type: 'reranker', value: setting.reranker, options: options.rerankers },
        { type: 'classifier', value: setting.classifier, options: options.classifiers },
      ];

      for (const check of checks) {
        const valid = isValidStrategy(check.value, check.options, check.type);
        if (!valid) {
          mismatches.push({ type: check.type, value: check.value, valid: false });
        }
      }

      return mismatches;
    },
    [options]
  );
}

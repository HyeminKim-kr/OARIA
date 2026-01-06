import { useMutation } from '@tanstack/react-query';
import { labApi, FeedbackParams, SearchTestResult, GenerateTestResult } from '@/lib/api';
import { SCORE_THRESHOLDS } from '../_lib';
import { FeedbackState } from '../_lib';

interface UseLabFeedbackParams {
  config: {
    query: string;
    limit: number;
    alpha: number;
    useReranker: boolean;
  };
  searchResult?: SearchTestResult;
  generateResult?: GenerateTestResult;
  onSuccess: (type: 'search' | 'generate', rating: 'good' | 'bad') => void;
}

export function useLabFeedback({
  config,
  searchResult,
  generateResult,
  onSuccess,
}: UseLabFeedbackParams) {
  const feedbackMutation = useMutation({
    mutationFn: (params: FeedbackParams) => labApi.saveFeedback(params),
    onSuccess: (_, variables) => {
      onSuccess(variables.type, variables.rating);
    },
  });

  const handleFeedback = (type: 'search' | 'generate', rating: 'good' | 'bad') => {
    const result = type === 'search' ? searchResult : generateResult;
    if (!result) return;

    let relevantCount: number | undefined;
    let lowRelevanceCount: number | undefined;

    if (type === 'search' && searchResult) {
      const chunks = searchResult.chunks;
      if (searchResult.parameters.useReranker) {
        relevantCount = chunks.filter(
          (c) => (c.rerankScore ?? c.score) >= SCORE_THRESHOLDS.LOW
        ).length;
        lowRelevanceCount = chunks.filter(
          (c) => (c.rerankScore ?? c.score) < SCORE_THRESHOLDS.LOW
        ).length;
      }
    }

    const topScore =
      type === 'search' && searchResult?.chunks[0]
        ? searchResult.chunks[0].rerankScore ?? searchResult.chunks[0].score
        : generateResult?.references[0]?.score ?? 0;

    const feedbackParams: FeedbackParams = {
      type,
      query: config.query,
      rating,
      parameters: {
        limit: config.limit,
        alpha: config.alpha,
        useReranker: config.useReranker,
        rerankerModel: type === 'search' ? searchResult?.parameters.rerankerModel : undefined,
      },
      resultSummary: {
        totalChunks:
          type === 'search'
            ? searchResult?.totalChunks ?? 0
            : generateResult?.references.length ?? 0,
        topScore,
        relevantCount,
        lowRelevanceCount,
        model: type === 'generate' ? generateResult?.model : undefined,
        tokensUsed: type === 'generate' ? generateResult?.tokensUsed : undefined,
      },
      searchLatencyMs: type === 'search' ? searchResult?.searchLatencyMs : generateResult?.searchLatencyMs,
      rerankLatencyMs: type === 'search' ? searchResult?.rerankLatencyMs : generateResult?.rerankLatencyMs,
      llmLatencyMs: type === 'generate' ? generateResult?.llmLatencyMs : undefined,
    };

    feedbackMutation.mutate(feedbackParams);
  };

  return {
    handleFeedback,
    isPending: feedbackMutation.isPending,
  };
}

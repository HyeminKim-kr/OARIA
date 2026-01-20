import { useQuery } from '@tanstack/react-query';
import { labApi } from '@/lib/api';

export function useLabStats(enabled: boolean) {
  const { data: feedbackStats } = useQuery({
    queryKey: ['lab', 'stats', 'feedback'],
    queryFn: () => labApi.getFeedbackStats(),
    enabled,
  });

  const { data: testLogStats } = useQuery({
    queryKey: ['lab', 'stats', 'logs'],
    queryFn: () => labApi.getTestLogStats(),
    enabled,
  });

  return {
    feedbackStats,
    testLogStats,
  };
}

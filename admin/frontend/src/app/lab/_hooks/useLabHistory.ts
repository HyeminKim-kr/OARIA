import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { labApi } from '@/lib/api';

type HistoryTypeFilter = 'search' | 'generate' | 'compare' | undefined;

export function useLabHistory(enabled: boolean) {
  const [page, setPage] = useState(1);
  const [typeFilter, setTypeFilter] = useState<HistoryTypeFilter>();
  const [selectedLogId, setSelectedLogId] = useState<string | null>(null);

  const { data: testLogs, refetch: refetchLogs } = useQuery({
    queryKey: ['lab', 'logs', page, typeFilter],
    queryFn: () => labApi.getTestLogs({ page, limit: 10, testType: typeFilter }),
    enabled,
  });

  const deleteLogMutation = useMutation({
    mutationFn: (id: string) => labApi.deleteTestLog(id),
    onSuccess: () => {
      refetchLogs();
      if (selectedLogId) setSelectedLogId(null);
    },
  });

  const { data: selectedLogDetail, isLoading: isLoadingLogDetail } = useQuery({
    queryKey: ['lab', 'log', selectedLogId],
    queryFn: () => labApi.getTestLog(selectedLogId!),
    enabled: !!selectedLogId,
  });

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
  };

  const handleTypeFilterChange = (filter: HistoryTypeFilter) => {
    setTypeFilter(filter);
    setPage(1);
  };

  const handleLogSelect = (logId: string) => {
    setSelectedLogId(selectedLogId === logId ? null : logId);
  };

  const handleLogDelete = (id: string) => {
    if (confirm('이 테스트 기록을 삭제하시겠습니까?')) {
      deleteLogMutation.mutate(id);
    }
  };

  return {
    page,
    typeFilter,
    testLogs,
    selectedLogId,
    selectedLogDetail,
    isLoadingLogDetail,
    isDeleting: deleteLogMutation.isPending,
    handlePageChange,
    handleTypeFilterChange,
    handleLogSelect,
    handleLogDelete,
  };
}

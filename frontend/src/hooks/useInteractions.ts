"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { interactionsApi } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

/**
 * 논문 목록의 좋아요/북마크 상태 bulk 조회
 */
export function usePaperInteractions(paperIds: string[]) {
  const { isAuthenticated } = useAuth();

  return useQuery({
    queryKey: ["paper-interactions", paperIds],
    queryFn: () => interactionsApi.getBulkStatus(paperIds),
    enabled: isAuthenticated && paperIds.length > 0,
    staleTime: 30_000,
  });
}

/**
 * 좋아요 토글 mutation
 */
export function useToggleLike() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (paperId: string) => interactionsApi.toggleLike(paperId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["paper-interactions"] });
      queryClient.invalidateQueries({ queryKey: ["papers"] });
      queryClient.invalidateQueries({ queryKey: ["paper"] });
      queryClient.invalidateQueries({ queryKey: ["my-likes"] });
    },
  });
}

/**
 * 북마크 토글 mutation
 */
export function useToggleBookmark() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      paperId,
      collectionId,
    }: {
      paperId: string;
      collectionId?: string;
    }) => interactionsApi.toggleBookmark(paperId, collectionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["paper-interactions"] });
      queryClient.invalidateQueries({ queryKey: ["my-bookmarks"] });
      queryClient.invalidateQueries({ queryKey: ["my-collections"] });
    },
  });
}

/**
 * 내 컬렉션 목록
 */
export function useMyCollections() {
  const { isAuthenticated } = useAuth();

  return useQuery({
    queryKey: ["my-collections"],
    queryFn: () => interactionsApi.getCollections(),
    enabled: isAuthenticated,
  });
}

/**
 * 내 북마크 목록 (페이지네이션, 컬렉션 필터)
 */
export function useMyBookmarks(
  page = 1,
  limit = 20,
  collectionId?: string
) {
  const { isAuthenticated } = useAuth();

  return useQuery({
    queryKey: ["my-bookmarks", page, limit, collectionId],
    queryFn: () => interactionsApi.getMyBookmarks(page, limit, collectionId),
    enabled: isAuthenticated,
  });
}

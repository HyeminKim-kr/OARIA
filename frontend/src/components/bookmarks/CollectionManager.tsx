"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  FolderPlus,
  Pencil,
  Trash2,
  Check,
  X,
  Loader2,
  FolderOpen,
} from "lucide-react";
import { interactionsApi } from "@/lib/api";
import { useMyCollections } from "@/hooks";

export function CollectionManager() {
  const queryClient = useQueryClient();
  const { data: collectionsData, isLoading } = useMyCollections();

  const [isCreating, setIsCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");

  const invalidateCollections = () => {
    queryClient.invalidateQueries({ queryKey: ["my-collections"] });
  };

  const createMutation = useMutation({
    mutationFn: (data: { name: string; description?: string }) =>
      interactionsApi.createCollection(data.name, data.description),
    onSuccess: () => {
      invalidateCollections();
      setIsCreating(false);
      setNewName("");
      setNewDescription("");
    },
  });

  const updateMutation = useMutation({
    mutationFn: (data: { id: string; name: string; description?: string }) =>
      interactionsApi.updateCollection(data.id, { name: data.name, description: data.description }),
    onSuccess: () => {
      invalidateCollections();
      setEditingId(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => interactionsApi.deleteCollection(id),
    onSuccess: () => {
      invalidateCollections();
    },
  });

  const handleCreate = () => {
    if (!newName.trim()) return;
    createMutation.mutate({ name: newName.trim(), description: newDescription.trim() || undefined });
  };

  const handleUpdate = (id: string) => {
    if (!editName.trim()) return;
    updateMutation.mutate({ id, name: editName.trim(), description: editDescription.trim() || undefined });
  };

  const handleDelete = (id: string, name: string) => {
    if (confirm(`"${name}" 컬렉션을 삭제하시겠습니까?\n북마크는 유지되지만 컬렉션 분류가 해제됩니다.`)) {
      deleteMutation.mutate(id);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-[var(--oaria-teal)]" />
      </div>
    );
  }

  const collections = collectionsData?.items || [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-[family-name:var(--font-outfit)] text-lg font-semibold text-[var(--foreground)]">
          컬렉션 관리
        </h3>
        {!isCreating && (
          <button
            onClick={() => setIsCreating(true)}
            className="flex items-center gap-1.5 rounded-lg bg-[var(--oaria-teal)] px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-[var(--oaria-light-teal)]"
          >
            <FolderPlus size={16} />
            새 컬렉션
          </button>
        )}
      </div>

      {/* Create Form */}
      {isCreating && (
        <div className="rounded-xl border-2 border-[var(--oaria-teal)]/30 bg-[var(--background)] p-4">
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="컬렉션 이름"
            className="mb-2 w-full rounded-lg border border-[var(--oaria-border)] bg-transparent px-3 py-2 text-sm outline-none focus:border-[var(--oaria-teal)]"
            autoFocus
          />
          <input
            type="text"
            value={newDescription}
            onChange={(e) => setNewDescription(e.target.value)}
            placeholder="설명 (선택)"
            className="mb-3 w-full rounded-lg border border-[var(--oaria-border)] bg-transparent px-3 py-2 text-sm outline-none focus:border-[var(--oaria-teal)]"
          />
          <div className="flex gap-2">
            <button
              onClick={handleCreate}
              disabled={!newName.trim() || createMutation.isPending}
              className="flex items-center gap-1 rounded-lg bg-[var(--oaria-teal)] px-3 py-1.5 text-sm text-white disabled:opacity-50"
            >
              {createMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
              생성
            </button>
            <button
              onClick={() => { setIsCreating(false); setNewName(""); setNewDescription(""); }}
              className="flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm text-[var(--oaria-text-secondary)] hover:bg-[var(--oaria-border)]/50"
            >
              <X size={14} />
              취소
            </button>
          </div>
        </div>
      )}

      {/* Collection List */}
      <div className="space-y-2">
        {collections.map((col) => (
          <div
            key={col.id}
            className="flex items-center justify-between rounded-xl border border-[var(--oaria-border)] bg-[var(--background)] p-4"
          >
            {editingId === col.id ? (
              <div className="flex-1 space-y-2">
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="w-full rounded-lg border border-[var(--oaria-border)] bg-transparent px-3 py-1.5 text-sm outline-none focus:border-[var(--oaria-teal)]"
                  autoFocus
                />
                <input
                  type="text"
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  placeholder="설명 (선택)"
                  className="w-full rounded-lg border border-[var(--oaria-border)] bg-transparent px-3 py-1.5 text-sm outline-none focus:border-[var(--oaria-teal)]"
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => handleUpdate(col.id)}
                    disabled={!editName.trim() || updateMutation.isPending}
                    className="flex items-center gap-1 rounded-lg bg-[var(--oaria-teal)] px-2.5 py-1 text-xs text-white disabled:opacity-50"
                  >
                    {updateMutation.isPending ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
                    저장
                  </button>
                  <button
                    onClick={() => setEditingId(null)}
                    className="flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs text-[var(--oaria-text-secondary)] hover:bg-[var(--oaria-border)]/50"
                  >
                    <X size={12} />
                    취소
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className="flex items-center gap-3">
                  <FolderOpen size={20} className="text-[var(--oaria-teal)]" />
                  <div>
                    <p className="text-sm font-medium text-[var(--foreground)]">
                      {col.name}
                      {col.is_default && (
                        <span className="ml-2 text-xs text-[var(--oaria-tagline)]">(기본)</span>
                      )}
                    </p>
                    {col.description && (
                      <p className="text-xs text-[var(--oaria-text-secondary)]">{col.description}</p>
                    )}
                    <p className="text-xs text-[var(--oaria-tagline)]">
                      {col.bookmark_count}개의 논문
                    </p>
                  </div>
                </div>
                {!col.is_default && (
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => {
                        setEditingId(col.id);
                        setEditName(col.name);
                        setEditDescription(col.description || "");
                      }}
                      className="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--oaria-text-secondary)] hover:bg-[var(--oaria-border)]/50 hover:text-[var(--oaria-teal)]"
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      onClick={() => handleDelete(col.id, col.name)}
                      disabled={deleteMutation.isPending}
                      className="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--oaria-text-secondary)] hover:bg-red-50 hover:text-red-500"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        ))}

        {collections.length === 0 && (
          <div className="rounded-xl border border-[var(--oaria-border)] bg-[var(--background)] p-6 text-center">
            <FolderOpen size={32} className="mx-auto mb-2 text-[var(--oaria-tagline)]" />
            <p className="text-sm text-[var(--oaria-text-secondary)]">
              컬렉션이 없습니다. 첫 북마크 시 자동으로 기본 컬렉션이 생성됩니다.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

import { RAGSettings, StrategiesResponse } from '@/lib/api';

// 전략 타입
export type StrategyType = 'chunker' | 'embedder' | 'retriever' | 'reranker' | 'classifier';

// 전략 옵션 인터페이스
export interface StrategyOptions {
  chunkers: string[];
  embedders: string[];
  retrievers: string[];
  rerankers: string[];
  classifiers: string[];
}

// 설정 폼 타입
export interface SettingFormData {
  name: string;
  description: string;
  chunker: string;
  embedder: string;
  retriever: string;
  reranker: string | null;
  classifier: string | null;
  parameters: { limit: number; alpha: number };
}

// Mismatch 정보
export interface SettingMismatch {
  type: StrategyType;
  value: string | null;
  valid: boolean;
}

// 패널 Props
export interface RAGSettingsPanelProps {
  strategies?: StrategiesResponse;
}

// SettingCard Props
export interface SettingCardProps {
  setting: RAGSettings;
  isEditing: boolean;
  editForm: Partial<RAGSettings>;
  options: StrategyOptions;
  mismatches: SettingMismatch[];
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onSaveEdit: () => void;
  onActivate: () => void;
  onDelete: () => void;
  onEditFormChange: (updates: Partial<RAGSettings>) => void;
  isUpdatePending: boolean;
  isActivatePending: boolean;
  isDeletePending: boolean;
}

// NewSettingForm Props
export interface NewSettingFormProps {
  form: SettingFormData;
  options: StrategyOptions;
  onChange: (updates: Partial<SettingFormData>) => void;
  onSubmit: () => void;
  onCancel: () => void;
  isPending: boolean;
}

// StrategySelect Props
export interface StrategySelectProps {
  label: string;
  value: string | null;
  options: string[];
  type: StrategyType;
  onChange: (value: string | null) => void;
  isValid?: boolean;
  showMismatchWarning?: boolean;
}

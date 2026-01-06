import { SearchTestResult } from '@/lib/api';

export type TestMode = 'search' | 'generate' | 'compare';

export type RelevanceLevel = 'high' | 'medium' | 'low' | 'irrelevant';

export interface RelevanceStyle {
  bg: string;
  text: string;
  label: string;
}

export interface CompareResults {
  withReranker?: SearchTestResult;
  withoutReranker?: SearchTestResult;
}

export interface FeedbackState {
  search?: 'good' | 'bad';
  generate?: 'good' | 'bad';
}

export interface ErrorInfo {
  type: 'no_data' | 'error';
  message: string;
}

export interface LabConfig {
  query: string;
  limit: number;
  alpha: number;
  useReranker: boolean;
}

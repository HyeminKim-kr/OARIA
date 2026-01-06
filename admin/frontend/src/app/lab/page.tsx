'use client';

import { useState } from 'react';
import { useLabExperiment, useLabHistory, useLabStats, useLabFeedback } from './_hooks';
import { extractErrorInfo } from './_lib';
import {
  LabHeader,
  LabStatsPanel,
  LabHelpPanel,
  LabHistoryPanel,
  LabConfigForm,
  LabSearchResults,
  LabGenerateResults,
  LabCompareResults,
  LabErrorState,
  LabEmptyState,
} from './_components';

export default function LabPage() {
  // Panel visibility state
  const [showStats, setShowStats] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showHelp, setShowHelp] = useState(false);

  // Core experiment logic
  const {
    mode,
    setMode,
    config,
    updateConfig,
    status,
    isLoading,
    error,
    handleTest,
    searchResult,
    generateResult,
    compareResults,
    feedbackSubmitted,
    setFeedbackSubmitted,
  } = useLabExperiment();

  // History panel
  const history = useLabHistory(showHistory);

  // Stats panel
  const { feedbackStats, testLogStats } = useLabStats(showStats);

  // Feedback
  const { handleFeedback, isPending: feedbackPending } = useLabFeedback({
    config,
    searchResult,
    generateResult,
    onSuccess: (type, rating) => {
      setFeedbackSubmitted((prev) => ({ ...prev, [type]: rating }));
    },
  });

  // Toggle handlers
  const handleToggleStats = () => {
    setShowStats(!showStats);
    if (!showStats) {
      setShowHistory(false);
      setShowHelp(false);
    }
  };

  const handleToggleHistory = () => {
    setShowHistory(!showHistory);
    if (!showHistory) {
      setShowHelp(false);
      setShowStats(false);
    }
  };

  const handleToggleHelp = () => {
    setShowHelp(!showHelp);
    if (!showHelp) {
      setShowHistory(false);
      setShowStats(false);
    }
  };

  // Error handling
  const errorInfo = extractErrorInfo(error);

  // Check if there are results to display
  const hasResults =
    searchResult || generateResult || compareResults.withReranker || compareResults.withoutReranker;

  return (
    <div className="space-y-6">
      <LabHeader
        status={status}
        showStats={showStats}
        showHistory={showHistory}
        showHelp={showHelp}
        onToggleStats={handleToggleStats}
        onToggleHistory={handleToggleHistory}
        onToggleHelp={handleToggleHelp}
      />

      {showStats && <LabStatsPanel feedbackStats={feedbackStats} testLogStats={testLogStats} />}

      {showHelp && <LabHelpPanel />}

      {showHistory && (
        <LabHistoryPanel
          page={history.page}
          typeFilter={history.typeFilter}
          testLogs={history.testLogs}
          selectedLogId={history.selectedLogId}
          selectedLogDetail={history.selectedLogDetail}
          isLoadingLogDetail={history.isLoadingLogDetail}
          isDeleting={history.isDeleting}
          onPageChange={history.handlePageChange}
          onTypeFilterChange={history.handleTypeFilterChange}
          onLogSelect={history.handleLogSelect}
          onLogDelete={history.handleLogDelete}
        />
      )}

      <LabConfigForm
        mode={mode}
        config={config}
        isLoading={isLoading}
        isAvailable={status?.available ?? false}
        onModeChange={setMode}
        onConfigChange={updateConfig}
        onTest={handleTest}
      />

      {mode === 'search' && searchResult && (
        <LabSearchResults
          result={searchResult}
          feedbackSubmitted={feedbackSubmitted}
          feedbackPending={feedbackPending}
          onFeedback={handleFeedback}
        />
      )}

      {mode === 'generate' && generateResult && (
        <LabGenerateResults
          result={generateResult}
          feedbackSubmitted={feedbackSubmitted}
          feedbackPending={feedbackPending}
          onFeedback={handleFeedback}
        />
      )}

      {mode === 'compare' &&
        (compareResults.withReranker || compareResults.withoutReranker) && (
          <LabCompareResults compareResults={compareResults} isLoading={isLoading} />
        )}

      {errorInfo && <LabErrorState errorInfo={errorInfo} />}

      {!hasResults && !isLoading && !errorInfo && <LabEmptyState />}
    </div>
  );
}

"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import {
  Send,
  Loader2,
  MessageSquare,
  Plus,
  FileText,
  FileOutput,
  Bot,
  ExternalLink,
  Copy,
  Check,
  X,
} from "lucide-react";
import { usePaperChat, PaperChatMessage } from "./hooks/usePaperChat";
import { ReferenceModal } from "@/components/chat/ReferenceModal";
import {
  paperChatApi,
  MessageReference,
  CitationFormat,
  PaperDetail,
} from "@/lib/api";

// 하이라이트 정보 타입
interface HighlightInfo {
  section: string;
  offset_start: number;
  offset_end: number;
}

interface PaperChatPanelProps {
  paper: PaperDetail;
  selectedText?: string;
  onClearSelectedText?: () => void;
  onHighlightRequest?: (info: HighlightInfo) => void;
}

export function PaperChatPanel({
  paper,
  selectedText,
  onClearSelectedText,
  onHighlightRequest,
}: PaperChatPanelProps) {
  const [input, setInput] = useState("");
  const [highlightContext, setHighlightContext] = useState<string | null>(null); // 선택된 텍스트 컨텍스트
  const [userContext, setUserContext] = useState<string | null>(null); // 사용자 입력 맥락
  const [showContextInput, setShowContextInput] = useState(false); // 맥락 입력창 표시
  const [contextInputValue, setContextInputValue] = useState(""); // 맥락 입력 임시값
  const [selectedReference, setSelectedReference] = useState<MessageReference | null>(null);
  const [showCitationModal, setShowCitationModal] = useState(false);
  const [citationLoading, setCitationLoading] = useState(false);
  const [citationResult, setCitationResult] = useState<string | null>(null);
  const [copiedCitation, setCopiedCitation] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const {
    messages,
    isLoading,
    statusMessage,
    sendMessage,
    clearMessages,
    requestSummary,
  } = usePaperChat({
    paperId: paper.id,
  });

  // 스크롤 자동 이동
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // 선택된 텍스트를 컨텍스트로 설정 (바로 전송하지 않음)
  const handleHighlightQuestion = () => {
    if (selectedText) {
      const truncated = selectedText.slice(0, 500);
      setHighlightContext(truncated);
      onClearSelectedText?.();
    }
  };

  // 맥락 추가 버튼 클릭
  const handleAddContext = () => {
    setShowContextInput(true);
    setContextInputValue(userContext || "");
  };

  // 맥락 저장
  const handleSaveContext = () => {
    if (contextInputValue.trim()) {
      setUserContext(contextInputValue.trim().slice(0, 1000));
    }
    setShowContextInput(false);
    setContextInputValue("");
  };

  // 인용 생성
  const handleCitation = async (format: CitationFormat = "apa") => {
    setCitationLoading(true);
    setCitationResult(null);
    setShowCitationModal(true);

    try {
      const response = await paperChatApi.citation(paper.id, { format });
      setCitationResult(response.data.citation);
    } catch (err) {
      console.error("Citation error:", err);
      setCitationResult("인용 정보 생성 중 오류가 발생했습니다.");
    } finally {
      setCitationLoading(false);
    }
  };

  // 인용 복사
  const handleCopyCitation = async () => {
    if (citationResult) {
      await navigator.clipboard.writeText(citationResult);
      setCopiedCitation(true);
      setTimeout(() => setCopiedCitation(false), 2000);
    }
  };

  // 폼 제출
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      // 하이라이트 + 사용자 맥락 결합
      const combinedContext = [highlightContext, userContext].filter(Boolean).join("\n\n---\n\n");
      sendMessage(input, combinedContext ? { highlightContext: combinedContext } : undefined);
      setInput("");
      setHighlightContext(null);
      setUserContext(null);
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Quick Actions */}
      <div className="mb-4 grid grid-cols-2 gap-3">
        <button
          onClick={handleHighlightQuestion}
          disabled={!selectedText && !highlightContext}
          className={`flex flex-col items-start gap-2 rounded-xl border border-[var(--oaria-border)] p-4 text-left transition-colors ${
            selectedText || highlightContext
              ? "hover:border-[var(--oaria-teal)] bg-[var(--oaria-teal)]/5"
              : "opacity-50 cursor-not-allowed"
          }`}
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--oaria-teal)]/10 text-[var(--oaria-teal)]">
            <MessageSquare size={20} />
          </div>
          <div>
            <p className="font-medium text-[var(--foreground)]">하이라이트 & 질문</p>
            <p className="text-xs text-[var(--oaria-tagline)]">
              {highlightContext ? "컨텍스트 설정됨" : selectedText ? "컨텍스트 추가" : "텍스트를 선택하세요"}
            </p>
          </div>
        </button>

        <button
          onClick={handleAddContext}
          className={`flex flex-col items-start gap-2 rounded-xl border border-[var(--oaria-border)] p-4 text-left transition-colors ${
            userContext
              ? "hover:border-[var(--oaria-teal)] bg-[var(--oaria-teal)]/5"
              : "hover:border-[var(--oaria-teal)]"
          }`}
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--oaria-teal)]/10 text-[var(--oaria-teal)]">
            <Plus size={20} />
          </div>
          <div>
            <p className="font-medium text-[var(--foreground)]">맥락 추가</p>
            <p className="text-xs text-[var(--oaria-tagline)]">
              {userContext ? "맥락 설정됨" : "배경 정보 입력"}
            </p>
          </div>
        </button>

        <button
          onClick={() => requestSummary("full")}
          disabled={isLoading}
          className={`flex flex-col items-start gap-2 rounded-xl border border-[var(--oaria-border)] p-4 text-left transition-colors ${
            isLoading ? "opacity-50 cursor-not-allowed" : "hover:border-[var(--oaria-teal)]"
          }`}
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--oaria-teal)]/10 text-[var(--oaria-teal)]">
            <FileText size={20} />
          </div>
          <div>
            <p className="font-medium text-[var(--foreground)]">요약 생성</p>
            <p className="text-xs text-[var(--oaria-tagline)]">핵심 내용 정리</p>
          </div>
        </button>

        <button
          onClick={() => handleCitation("apa")}
          className="flex flex-col items-start gap-2 rounded-xl border border-[var(--oaria-border)] p-4 text-left transition-colors hover:border-[var(--oaria-teal)]"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--oaria-teal)]/10 text-[var(--oaria-teal)]">
            <FileOutput size={20} />
          </div>
          <div>
            <p className="font-medium text-[var(--foreground)]">인용 정보</p>
            <p className="text-xs text-[var(--oaria-tagline)]">참고문헌 내보내기</p>
          </div>
        </button>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-8">
            <div className="w-12 h-12 rounded-full bg-[var(--oaria-teal)]/10 flex items-center justify-center mb-4">
              <Bot size={24} className="text-[var(--oaria-teal)]" />
            </div>
            <p className="text-sm text-[var(--oaria-text-secondary)]">
              이 논문에 대해 궁금한 점을 물어보세요
            </p>
            <p className="text-xs text-[var(--oaria-tagline)] mt-1">
              AI가 논문 내용을 기반으로 답변합니다
            </p>
          </div>
        ) : (
          messages.map((message) => (
            <MessageBubble
              key={message.id}
              message={message}
              isLoading={isLoading}
              onReferenceClick={setSelectedReference}
              onHighlightRequest={onHighlightRequest}
            />
          ))
        )}

        {/* 상태 메시지 */}
        {isLoading && statusMessage && (
          <div className="flex items-center gap-2 text-[var(--oaria-text-secondary)]">
            <Loader2 size={16} className="animate-spin text-[var(--oaria-teal)]" />
            <span className="text-sm">{statusMessage}</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t border-[var(--oaria-border)] pt-4">
        {/* 컨텍스트 표시 영역 */}
        {(highlightContext || userContext) && (
          <div className="mb-3 space-y-2">
            {/* 하이라이트 컨텍스트 */}
            {highlightContext && (
              <div className="p-3 rounded-lg bg-[var(--oaria-teal)]/10 border border-[var(--oaria-teal)]/30">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 mb-1">
                      <MessageSquare size={12} className="text-[var(--oaria-teal)]" />
                      <span className="text-xs font-medium text-[var(--oaria-teal)]">선택된 텍스트</span>
                    </div>
                    <p className="text-xs text-[var(--oaria-text-secondary)] line-clamp-2">
                      "{highlightContext.slice(0, 150)}{highlightContext.length > 150 ? "..." : ""}"
                    </p>
                  </div>
                  <button
                    onClick={() => setHighlightContext(null)}
                    className="p-1 rounded-full hover:bg-[var(--oaria-border)]/50 transition-colors flex-shrink-0"
                  >
                    <X size={14} className="text-[var(--oaria-text-secondary)]" />
                  </button>
                </div>
              </div>
            )}

            {/* 사용자 맥락 */}
            {userContext && (
              <div className="p-3 rounded-lg bg-purple-500/10 border border-purple-500/30">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 mb-1">
                      <Plus size={12} className="text-purple-500" />
                      <span className="text-xs font-medium text-purple-500">추가 맥락</span>
                    </div>
                    <p className="text-xs text-[var(--oaria-text-secondary)] line-clamp-2">
                      {userContext.slice(0, 150)}{userContext.length > 150 ? "..." : ""}
                    </p>
                  </div>
                  <button
                    onClick={() => setUserContext(null)}
                    className="p-1 rounded-full hover:bg-[var(--oaria-border)]/50 transition-colors flex-shrink-0"
                  >
                    <X size={14} className="text-[var(--oaria-text-secondary)]" />
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="flex items-center gap-2 rounded-xl bg-[var(--oaria-border)]/30 px-4 py-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={
                highlightContext || userContext
                  ? "컨텍스트를 참고하여 질문하세요..."
                  : "논문에 대해 질문하세요..."
              }
              disabled={isLoading}
              className="flex-1 bg-transparent text-sm text-[var(--foreground)] placeholder:text-[var(--oaria-tagline)] focus:outline-none disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--oaria-teal)] text-white hover:bg-[var(--oaria-teal)]/90 disabled:bg-[var(--oaria-border)] disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Send size={16} />
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Reference Modal */}
      {selectedReference && (
        <ReferenceModal
          reference={{
            ...selectedReference,
            journal: selectedReference.journal || "",
            year: selectedReference.year || 0,
          }}
          onClose={() => setSelectedReference(null)}
        />
      )}

      {/* Citation Modal */}
      {showCitationModal && (
        <QuickActionModal
          title="인용 정보"
          onClose={() => setShowCitationModal(false)}
        >
          {citationLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 size={32} className="animate-spin text-[var(--oaria-teal)]" />
            </div>
          ) : (
            <div className="space-y-4">
              {/* 형식 선택 버튼 */}
              <div className="flex flex-wrap gap-2">
                {(["apa", "mla", "chicago", "harvard", "vancouver", "bibtex"] as CitationFormat[]).map((format) => (
                  <button
                    key={format}
                    onClick={() => handleCitation(format)}
                    className="px-3 py-1 text-xs rounded-full border border-[var(--oaria-border)] hover:border-[var(--oaria-teal)] hover:text-[var(--oaria-teal)]"
                  >
                    {format.toUpperCase()}
                  </button>
                ))}
              </div>

              {/* 인용 결과 */}
              <div className="relative">
                <pre className="p-4 rounded-lg bg-[var(--oaria-border)]/30 text-sm whitespace-pre-wrap font-mono">
                  {citationResult}
                </pre>
                <button
                  onClick={handleCopyCitation}
                  className="absolute top-2 right-2 p-2 rounded-lg bg-[var(--background)] border border-[var(--oaria-border)] hover:border-[var(--oaria-teal)]"
                >
                  {copiedCitation ? (
                    <Check size={16} className="text-green-500" />
                  ) : (
                    <Copy size={16} className="text-[var(--oaria-text-secondary)]" />
                  )}
                </button>
              </div>
            </div>
          )}
        </QuickActionModal>
      )}

      {/* Context Input Modal */}
      {showContextInput && (
        <QuickActionModal
          title="맥락 추가"
          onClose={() => {
            setShowContextInput(false);
            setContextInputValue("");
          }}
        >
          <div className="space-y-4">
            <p className="text-sm text-[var(--oaria-text-secondary)]">
              질문에 참고할 배경 정보나 맥락을 입력하세요.
            </p>
            <textarea
              value={contextInputValue}
              onChange={(e) => setContextInputValue(e.target.value)}
              placeholder="예: 이 연구는 폐암 환자 치료에 관한 것입니다. 특히 면역치료 효과에 대해 알고 싶습니다..."
              className="w-full h-32 p-3 rounded-lg border border-[var(--oaria-border)] bg-transparent text-sm text-[var(--foreground)] placeholder:text-[var(--oaria-tagline)] focus:outline-none focus:border-[var(--oaria-teal)] resize-none"
              maxLength={1000}
            />
            <div className="flex items-center justify-between">
              <span className="text-xs text-[var(--oaria-tagline)]">
                {contextInputValue.length}/1000
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    setShowContextInput(false);
                    setContextInputValue("");
                  }}
                  className="px-4 py-2 text-sm rounded-lg border border-[var(--oaria-border)] hover:bg-[var(--oaria-border)]/30"
                >
                  취소
                </button>
                <button
                  onClick={handleSaveContext}
                  disabled={!contextInputValue.trim()}
                  className="px-4 py-2 text-sm rounded-lg bg-[var(--oaria-teal)] text-white hover:bg-[var(--oaria-teal)]/90 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  저장
                </button>
              </div>
            </div>
          </div>
        </QuickActionModal>
      )}
    </div>
  );
}

// 메시지 버블 컴포넌트
function MessageBubble({
  message,
  isLoading,
  onReferenceClick,
  onHighlightRequest,
}: {
  message: PaperChatMessage;
  isLoading: boolean;
  onReferenceClick: (ref: MessageReference) => void;
  onHighlightRequest?: (info: HighlightInfo) => void;
}) {
  const isUser = message.role === "user";

  return (
    <div className={`flex gap-2 ${isUser ? "justify-end" : ""}`}>
      {/* AI Avatar */}
      {!isUser && (
        <div className="w-6 h-6 rounded-full flex-shrink-0 flex items-center justify-center bg-[var(--oaria-teal)]">
          <Bot size={12} className="text-white" />
        </div>
      )}

      {/* Content */}
      <div
        className={`${
          isUser
            ? "max-w-[80%] bg-[var(--oaria-teal)] text-white rounded-xl rounded-br-sm px-3 py-2"
            : "flex-1"
        }`}
      >
        {isUser ? (
          <div className="text-sm whitespace-pre-wrap">{message.content}</div>
        ) : (
          <>
            <div className="prose prose-sm max-w-none text-[var(--foreground)]">
              <ReactMarkdown>{message.content}</ReactMarkdown>
              {/* 스트리밍 중 커서 */}
              {message.isStreaming && isLoading && message.content && (
                <span className="inline-block w-1.5 h-4 bg-[var(--oaria-teal)] ml-0.5 animate-pulse" />
              )}
            </div>

            {/* 근거 섹션 - 같은 논문 내 참조 위치 */}
            {message.references && message.references.length > 0 && (
              <div className="mt-3 pt-3 border-t border-[var(--oaria-border)]">
                <div className="flex items-center gap-1.5 mb-2">
                  <FileText size={12} className="text-[var(--oaria-teal)]" />
                  <span className="text-xs font-medium text-[var(--oaria-text-secondary)]">
                    근거 섹션
                  </span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {message.references.slice(0, 5).map((ref, idx) => (
                    <button
                      key={`${ref.paper_id}-${ref.section}-${idx}`}
                      onClick={() => {
                        // 논문 본문에 하이라이트 요청
                        onHighlightRequest?.({
                          section: ref.section,
                          offset_start: ref.offset_start,
                          offset_end: ref.offset_end,
                        });
                      }}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[var(--oaria-teal)]/10 hover:bg-[var(--oaria-teal)]/20 transition-colors text-left group"
                    >
                      <span className="text-xs font-medium text-[var(--oaria-teal)]">
                        {ref.section}
                      </span>
                      <ExternalLink
                        size={10}
                        className="text-[var(--oaria-teal)] opacity-60 group-hover:opacity-100"
                      />
                    </button>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// Quick Action 모달 컴포넌트
function QuickActionModal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
}) {
  // ESC 키로 닫기
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-2xl max-h-[80vh] mx-4 bg-[var(--background)] rounded-2xl shadow-2xl overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--oaria-border)]">
          <h2 className="font-[family-name:var(--font-outfit)] text-lg font-semibold text-[var(--foreground)]">
            {title}
          </h2>
          <button
            onClick={onClose}
            className="p-2 rounded-full hover:bg-[var(--oaria-border)]/50 transition-colors"
          >
            <X size={20} className="text-[var(--oaria-text-secondary)]" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">{children}</div>
      </div>
    </div>
  );
}

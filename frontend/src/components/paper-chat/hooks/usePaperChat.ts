"use client";

import { useState, useCallback, useRef } from "react";
import { fetchWithAuth, paperChatApi, MessageReference, SummaryType } from "@/lib/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface PaperChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  references?: MessageReference[];
  isStreaming?: boolean;
  isSummary?: boolean;  // 요약 메시지 표시
}

export interface UsePaperChatOptions {
  paperId: string;
  onConversationCreated?: (conversationId: string) => void;
}

export function usePaperChat({ paperId, onConversationCreated }: UsePaperChatOptions) {
  const [messages, setMessages] = useState<PaperChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // 대화 히스토리 로드
  const loadMessages = useCallback(async (convId: string) => {
    try {
      const response = await paperChatApi.getMessages(paperId, convId);
      const loadedMessages: PaperChatMessage[] = response.data.items.map((m) => ({
        id: m.id,
        role: m.role as "user" | "assistant",
        content: m.content,
        references: m.references || undefined,
      }));
      setMessages(loadedMessages);
      setConversationId(convId);
    } catch (err) {
      console.error("Failed to load messages:", err);
      setError("메시지를 불러오는데 실패했습니다.");
    }
  }, [paperId]);

  // 질문 전송 (SSE 스트리밍)
  const sendMessage = useCallback(async (
    question: string,
    options?: {
      includeRelated?: boolean;
      highlightContext?: string;
    }
  ) => {
    if (!question.trim() || isLoading) return;

    setIsLoading(true);
    setError(null);
    setStatusMessage("");

    // 사용자 메시지 추가
    const userMessage: PaperChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: question,
    };
    setMessages((prev) => [...prev, userMessage]);

    // AI 응답 placeholder 추가
    const assistantMessageId = (Date.now() + 1).toString();
    setMessages((prev) => [
      ...prev,
      {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        references: [],
        isStreaming: true,
      },
    ]);

    // AbortController 생성
    abortControllerRef.current = new AbortController();

    try {
      const response = await fetchWithAuth(`${API_BASE_URL}/ai/papers/${paperId}/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question,
          conversation_id: conversationId,
          include_related: options?.includeRelated ?? false,
          highlight_context: options?.highlightContext,
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error("No response body");
      }

      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            continue;
          }

          if (line.startsWith("data: ")) {
            const dataStr = line.slice(6);
            try {
              const data = JSON.parse(dataStr);

              // status 이벤트
              if (data.status && data.message) {
                setStatusMessage(data.message);
              }

              // token 이벤트
              if (data.token) {
                setStatusMessage("");
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMessageId
                      ? { ...msg, content: msg.content + data.token }
                      : msg
                  )
                );
              }

              // references 이벤트
              if (data.references) {
                setStatusMessage("");
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMessageId
                      ? { ...msg, references: data.references }
                      : msg
                  )
                );
              }

              // error 이벤트
              if (data.error) {
                setError(data.error);
              }

              // done 이벤트
              if (data.conversation_id) {
                const newConvId = data.conversation_id;
                if (!conversationId) {
                  setConversationId(newConvId);
                  onConversationCreated?.(newConvId);
                }

                // 스트리밍 완료 표시
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMessageId
                      ? { ...msg, isStreaming: false }
                      : msg
                  )
                );
              }
            } catch {
              // JSON 파싱 실패 시 무시
            }
          }
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        // 사용자가 취소한 경우
        return;
      }

      console.error("Paper chat error:", err);
      setError("응답을 생성하는 중 오류가 발생했습니다.");

      // 에러 메시지로 업데이트
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId
            ? {
                ...msg,
                content: "죄송합니다. 응답을 생성하는 중 오류가 발생했습니다. 다시 시도해주세요.",
                isStreaming: false,
              }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
      setStatusMessage("");
      abortControllerRef.current = null;
    }
  }, [paperId, conversationId, isLoading, onConversationCreated]);

  // 응답 생성 취소
  const cancelGeneration = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsLoading(false);
      setStatusMessage("");
    }
  }, []);

  // 새 대화 시작
  const clearMessages = useCallback(() => {
    setMessages([]);
    setConversationId(null);
    setError(null);
  }, []);

  // 요약 요청 (SSE 스트리밍으로 채팅에 표시)
  const requestSummary = useCallback(async (summaryType: SummaryType = "full") => {
    if (isLoading) return;

    setIsLoading(true);
    setError(null);
    setStatusMessage("요약을 생성하고 있습니다...");

    // 사용자 요청 메시지 추가
    const userMessage: PaperChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: summaryType === "full"
        ? "이 논문을 요약해주세요."
        : `이 논문의 ${summaryType} 부분을 요약해주세요.`,
    };
    setMessages((prev) => [...prev, userMessage]);

    // AI 응답 placeholder 추가
    const assistantMessageId = (Date.now() + 1).toString();
    setMessages((prev) => [
      ...prev,
      {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        isStreaming: true,
        isSummary: true,
      },
    ]);

    // AbortController 생성
    abortControllerRef.current = new AbortController();

    try {
      const response = await fetchWithAuth(`${API_BASE_URL}/ai/papers/${paperId}/summarize`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          type: summaryType,
          stream: true,
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error("No response body");
      }

      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            continue;
          }

          if (line.startsWith("data: ")) {
            const dataStr = line.slice(6);
            try {
              const data = JSON.parse(dataStr);

              // token 이벤트
              if (data.token) {
                setStatusMessage("");
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMessageId
                      ? { ...msg, content: msg.content + data.token }
                      : msg
                  )
                );
              }

              // error 이벤트
              if (data.error) {
                setError(data.error);
              }

              // done 이벤트
              if (data.status === "completed") {
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMessageId
                      ? { ...msg, isStreaming: false }
                      : msg
                  )
                );
              }
            } catch {
              // JSON 파싱 실패 시 무시
            }
          }
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        return;
      }

      console.error("Summary error:", err);
      setError("요약을 생성하는 중 오류가 발생했습니다.");

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId
            ? {
                ...msg,
                content: "죄송합니다. 요약을 생성하는 중 오류가 발생했습니다. 다시 시도해주세요.",
                isStreaming: false,
              }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
      setStatusMessage("");
      abortControllerRef.current = null;
    }
  }, [paperId, isLoading]);

  return {
    messages,
    isLoading,
    statusMessage,
    conversationId,
    error,
    sendMessage,
    loadMessages,
    clearMessages,
    cancelGeneration,
    requestSummary,
  };
}

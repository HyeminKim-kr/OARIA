"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import {
  Search,
  Bot,
  MessageSquare,
  BarChart3,
  Loader2,
  CheckCircle2,
  Circle,
  ChevronDown,
  ChevronUp,
  Mic2,
  FileText,
  Target,
  Clock,
  X,
  Brain,
  ArrowLeft,
  History,
  Sparkles,
  Users,
  Quote,
  Volume2,
} from "lucide-react";
import { podcastApi, PodcastSSEEvent, PodcastDialogueScript, PodcastReference, fetchWithAuth } from "@/lib/api";

// ─────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────

type NodeStatus = "pending" | "active" | "completed" | "error";

interface NodeProgress {
  id: string;
  label: string;
  status: NodeStatus;
  icon: React.ReactNode;
  description: string;
}

interface Feature {
  icon: React.ReactNode;
  title: string;
  description: string;
}

interface FAQ {
  question: string;
  answer: string;
}

interface ActivityLog {
  id: string;
  timestamp: Date;
  type: "thinking" | "action" | "result" | "error";
  title: string;
  description?: string;
  nodeId?: string;
}

// DialogueTurn, DialogueScript, and PodcastReference are imported from @/lib/api

// ─────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────

const createInitialNodes = (): NodeProgress[] => [
  { id: "rag_search", label: "논문 검색", status: "pending", icon: <Search size={16} />, description: "관련 논문을 RAG로 검색합니다" },
  { id: "paper_analysis", label: "논문 분석", status: "pending", icon: <Brain size={16} />, description: "검색된 논문에서 핵심 내용을 분석합니다" },
  { id: "script_generation", label: "스크립트 생성", status: "pending", icon: <FileText size={16} />, description: "대화형 팟캐스트 스크립트를 생성합니다" },
  { id: "tts_generation", label: "음성 생성", status: "pending", icon: <Volume2 size={16} />, description: "OpenAI TTS로 음성을 생성합니다" },
];

const features: Feature[] = [
  {
    icon: <Search size={28} className="text-[var(--oaria-teal)]" />,
    title: "RAG 기반 콘텐츠",
    description: "실제 암 연구 논문을 기반으로 정확하고 신뢰할 수 있는 콘텐츠를 생성합니다.",
  },
  {
    icon: <Quote size={28} className="text-[var(--oaria-teal)]" />,
    title: "인용 포함",
    description: "모든 주요 주장에 [1], [2] 형태의 인용을 포함하여 근거를 제시합니다.",
  },
  {
    icon: <Users size={28} className="text-[var(--oaria-teal)]" />,
    title: "다양한 스타일",
    description: "두 호스트 대화, 인터뷰, 단독 발표 등 다양한 팟캐스트 형식을 지원합니다.",
  },
  {
    icon: <Clock size={28} className="text-[var(--oaria-teal)]" />,
    title: "맞춤 길이",
    description: "5분, 10분, 15분 등 원하는 에피소드 길이를 선택할 수 있습니다.",
  },
];

const faqs: FAQ[] = [
  {
    question: "어떤 종류의 주제로 팟캐스트를 만들 수 있나요?",
    answer: "OARIA의 논문 데이터베이스에 있는 암 연구 관련 주제라면 무엇이든 가능합니다. 예: 'EGFR 표적 치료의 최신 동향', '면역항암제의 작용 기전', 'TNBC 치료 옵션 비교' 등",
  },
  {
    question: "생성된 스크립트의 정확성은 어떻게 보장되나요?",
    answer: "모든 콘텐츠는 RAG(Retrieval-Augmented Generation)을 통해 실제 논문을 참조하여 생성됩니다. 각 주장에는 인용 번호가 포함되어 있어 원본 논문을 확인할 수 있습니다.",
  },
  {
    question: "스크립트 스타일은 어떤 것들이 있나요?",
    answer: "세 가지 스타일을 지원합니다: 1) 두 호스트 대화 - Alex와 Sam이 주고받는 자연스러운 대화, 2) 인터뷰 - 호스트가 전문가를 인터뷰하는 형식, 3) 단독 발표 - 한 명의 내레이터가 설명하는 형식",
  },
  {
    question: "생성된 스크립트는 어떻게 활용할 수 있나요?",
    answer: "생성된 스크립트는 실제 팟캐스트 녹음, 교육 자료, 연구 발표 준비 등에 활용할 수 있습니다. TTS 기능을 통해 오디오 파일로 변환하는 것도 계획 중입니다.",
  },
];

// ─────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────

export default function PodcastPage() {
  // View state
  const [viewMode, setViewMode] = useState<"landing" | "generate">("landing");

  // Form state
  const [goal, setGoal] = useState("");
  const [duration, setDuration] = useState<"short" | "medium" | "long">("short");
  const [style, setStyle] = useState<"two_hosts" | "interview" | "solo">("two_hosts");
  const [language, setLanguage] = useState<"ko" | "en">("ko");

  // Generation state
  const [isLoading, setIsLoading] = useState(false);
  const [nodes, setNodes] = useState<NodeProgress[]>(createInitialNodes());
  const [activityLogs, setActivityLogs] = useState<ActivityLog[]>([]);
  const [showActivitySidebar, setShowActivitySidebar] = useState(true);
  const [elapsedTime, setElapsedTime] = useState(0);

  // Result state
  const [script, setScript] = useState<PodcastDialogueScript | null>(null);
  const [references, setReferences] = useState<PodcastReference[]>([]);
  const [episodeId, setEpisodeId] = useState<string | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // FAQ expansion state
  const [expandedFaq, setExpandedFaq] = useState<number | null>(null);

  // Timer ref
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (abortControllerRef.current) abortControllerRef.current.abort();
    };
  }, []);

  // Add activity log
  const addLog = (log: Omit<ActivityLog, "id" | "timestamp">) => {
    setActivityLogs(prev => [{
      ...log,
      id: `log-${Date.now()}-${Math.random()}`,
      timestamp: new Date(),
    }, ...prev]);
  };

  // Update node status
  const updateNode = (nodeId: string, status: NodeStatus) => {
    setNodes(prev => prev.map(n =>
      n.id === nodeId ? { ...n, status } : n
    ));
  };

  // Start generation
  const handleGenerate = async () => {
    if (!goal.trim()) return;

    setIsLoading(true);
    setError(null);
    setScript(null);
    setReferences([]);
    setEpisodeId(null);
    setAudioUrl(null);
    setNodes(createInitialNodes());
    setActivityLogs([]);
    setElapsedTime(0);
    setViewMode("generate");

    // Start timer
    const startTime = Date.now();
    timerRef.current = setInterval(() => {
      setElapsedTime(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);

    addLog({
      type: "thinking",
      title: "팟캐스트 생성 시작",
      description: `목표: ${goal}`,
    });

    // Create abort controller for cancellation
    abortControllerRef.current = new AbortController();

    try {
      const streamUrl = podcastApi.generateStreamUrl();
      const response = await fetchWithAuth(streamUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          goal: goal.trim(),
          duration,
          style,
          paper_mode: "auto",
          language,
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";
      let currentEventType = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("event:")) {
            currentEventType = line.substring(6).trim();
          } else if (line.startsWith("data:")) {
            const dataStr = line.substring(5).trim();
            if (!dataStr) continue;

            try {
              const data: PodcastSSEEvent = JSON.parse(dataStr);
              handleSSEEvent(currentEventType, data);
            } catch (e) {
              console.error("Failed to parse SSE data:", e);
            }
          }
        }
      }
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        addLog({ type: "error", title: "생성 취소됨" });
      } else {
        console.error("Podcast generation failed:", err);
        setError((err as Error).message || "생성 중 오류가 발생했습니다.");
        addLog({
          type: "error",
          title: "생성 실패",
          description: (err as Error).message,
        });
      }
    } finally {
      setIsLoading(false);
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
  };

  // Handle SSE events
  const handleSSEEvent = (eventType: string, data: PodcastSSEEvent) => {
    switch (eventType) {
      case "status":
        // Handle TTS generation status
        if (data.status === "generating_audio") {
          updateNode("tts_generation", "active");
        } else if (data.status === "audio_complete") {
          updateNode("tts_generation", "completed");
        }
        addLog({
          type: "thinking",
          title: data.status || "상태 업데이트",
          description: data.message,
        });
        break;

      case "task_start":
        if (data.task_name) {
          const taskMap: Record<string, string> = {
            "RAG Search": "rag_search",
            "Paper Analysis": "paper_analysis",
            "Script Generation": "script_generation",
          };
          const nodeId = taskMap[data.task_name];
          if (nodeId) updateNode(nodeId, "active");

          addLog({
            type: "action",
            title: `${data.task_name} 시작`,
            description: `태스크 ${data.task_index}/${data.total_tasks}`,
            nodeId,
          });
        }
        break;

      case "task_complete":
        if (data.task_name) {
          const taskMap: Record<string, string> = {
            "RAG Search": "rag_search",
            "Paper Analysis": "paper_analysis",
            "Script Generation": "script_generation",
          };
          const nodeId = taskMap[data.task_name];
          if (nodeId) updateNode(nodeId, "completed");

          addLog({
            type: "result",
            title: `${data.task_name} 완료`,
            description: data.summary || `${data.duration_ms}ms`,
            nodeId,
          });
        }
        break;

      case "gate2_warning":
        addLog({
          type: "error",
          title: "검색 품질 경고",
          description: data.message || "검색 결과의 관련성이 낮습니다.",
        });
        break;

      case "script":
        if (data.script) {
          setScript(data.script as PodcastDialogueScript);
        }
        if (data.references) {
          setReferences(data.references);
        }
        break;

      case "done":
        setEpisodeId(data.episode_id || null);
        if (data.audio_url) {
          setAudioUrl(data.audio_url);
        }
        addLog({
          type: "result",
          title: "팟캐스트 생성 완료",
          description: data.audio_url ? "스크립트와 음성이 생성되었습니다." : "스크립트가 생성되었습니다.",
        });
        break;

      case "error":
        setError(data.error || "알 수 없는 오류");
        addLog({
          type: "error",
          title: "오류 발생",
          description: data.error,
        });
        break;
    }
  };

  // Cancel generation
  const handleCancel = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  // Reset to landing
  const handleReset = () => {
    setViewMode("landing");
    setGoal("");
    setScript(null);
    setReferences([]);
    setEpisodeId(null);
    setAudioUrl(null);
    setError(null);
    setNodes(createInitialNodes());
    setActivityLogs([]);
    setElapsedTime(0);
  };

  // Format elapsed time
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  // ─────────────────────────────────────────────────────────────
  // Render Landing View
  // ─────────────────────────────────────────────────────────────

  if (viewMode === "landing") {
    return (
      <div className="h-full flex flex-col overflow-hidden">
        {/* Navigation Tabs */}
        <div className="bg-[var(--background)]">
          <div className="flex items-center justify-center">
            <div className="flex items-center gap-6">
              <Link href="/ask" className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-colors">
                <MessageSquare size={20} />
                Ask AI
              </Link>
              <Link href="/main" className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-colors">
                <Search size={20} />
                Search Papers
              </Link>
              <Link href="/agents" className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-[var(--oaria-teal)] text-[var(--oaria-teal)]">
                <Bot size={20} />
                Agents
              </Link>
              <Link href="/dashboard" className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-colors">
                <BarChart3 size={20} />
                Dashboard
              </Link>
            </div>
          </div>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-4xl mx-auto px-6 py-8">
            {/* Back Button */}
            <Link href="/agents" className="inline-flex items-center gap-2 text-sm text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] mb-6 transition-colors">
              <ArrowLeft size={16} />
              모든 에이전트
            </Link>

            {/* Hero Section */}
            <div className="text-center mb-12">
              <div className="w-20 h-20 rounded-2xl bg-purple-500 flex items-center justify-center mx-auto mb-6 text-white">
                <Mic2 size={40} />
              </div>
              <h1 className="font-[family-name:var(--font-outfit)] text-4xl font-bold mb-4">
                Podcast Agent
              </h1>
              <p className="font-[family-name:var(--font-dm-sans)] text-lg text-[var(--oaria-text-secondary)] max-w-2xl mx-auto mb-8">
                암 연구 논문을 기반으로 팟캐스트 스크립트를 자동 생성합니다.
                <br />
                RAG 기반 인용과 다양한 대화 스타일을 지원합니다.
              </p>

              {/* CTA Buttons */}
              <div className="flex items-center justify-center gap-4">
                <button
                  onClick={() => setViewMode("generate")}
                  className="px-8 py-4 rounded-xl bg-[var(--oaria-teal)] text-white font-[family-name:var(--font-dm-sans)] font-semibold hover:bg-[#0B7A70] transition-colors flex items-center gap-2"
                >
                  <Sparkles size={20} />
                  팟캐스트 만들기
                </button>
                <Link
                  href="/agents/podcast/history"
                  className="px-8 py-4 rounded-xl border-2 border-[var(--oaria-border-strong)] text-[var(--foreground)] font-[family-name:var(--font-dm-sans)] font-semibold hover:border-[var(--oaria-teal)] transition-colors flex items-center gap-2"
                >
                  <History size={20} />
                  내 기록 보기
                </Link>
              </div>
            </div>

            {/* Features Section */}
            <div className="mb-16">
              <h2 className="font-[family-name:var(--font-outfit)] text-2xl font-semibold text-center mb-8">
                주요 기능
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {features.map((feature, idx) => (
                  <div
                    key={idx}
                    className="p-6 rounded-xl border-2 border-[var(--oaria-border)] bg-[var(--background)] hover:border-[var(--oaria-teal)]/30 transition-colors"
                  >
                    <div className="w-12 h-12 rounded-xl bg-[var(--oaria-teal)]/10 flex items-center justify-center mb-4">
                      {feature.icon}
                    </div>
                    <h3 className="font-[family-name:var(--font-outfit)] text-lg font-semibold mb-2">
                      {feature.title}
                    </h3>
                    <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)]">
                      {feature.description}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            {/* FAQ Section */}
            <div className="mb-16">
              <h2 className="font-[family-name:var(--font-outfit)] text-2xl font-semibold text-center mb-8">
                자주 묻는 질문
              </h2>
              <div className="space-y-4">
                {faqs.map((faq, idx) => (
                  <div
                    key={idx}
                    className="border-2 border-[var(--oaria-border)] rounded-xl overflow-hidden"
                  >
                    <button
                      onClick={() => setExpandedFaq(expandedFaq === idx ? null : idx)}
                      className="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-[var(--oaria-border)]/30 transition-colors"
                    >
                      <span className="font-[family-name:var(--font-dm-sans)] font-medium">
                        {faq.question}
                      </span>
                      {expandedFaq === idx ? (
                        <ChevronUp size={20} className="text-[var(--oaria-text-secondary)]" />
                      ) : (
                        <ChevronDown size={20} className="text-[var(--oaria-text-secondary)]" />
                      )}
                    </button>
                    {expandedFaq === idx && (
                      <div className="px-6 pb-4">
                        <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)]">
                          {faq.answer}
                        </p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ─────────────────────────────────────────────────────────────
  // Render Generate View
  // ─────────────────────────────────────────────────────────────

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Navigation Tabs */}
      <div className="bg-[var(--background)]">
        <div className="flex items-center justify-center">
          <div className="flex items-center gap-6">
            <Link href="/ask" className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-colors">
              <MessageSquare size={20} />
              Ask AI
            </Link>
            <Link href="/main" className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-colors">
              <Search size={20} />
              Search Papers
            </Link>
            <Link href="/agents" className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-[var(--oaria-teal)] text-[var(--oaria-teal)]">
              <Bot size={20} />
              Agents
            </Link>
            <Link href="/dashboard" className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-colors">
              <BarChart3 size={20} />
              Dashboard
            </Link>
          </div>
        </div>
      </div>

      {/* Main Content with Sidebar */}
      <div className="flex-1 flex overflow-hidden">
        {/* Main Area */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-3xl mx-auto">
            {/* Back Button */}
            <button
              onClick={handleReset}
              className="inline-flex items-center gap-2 text-sm text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] mb-6 transition-colors"
            >
              <ArrowLeft size={16} />
              처음으로
            </button>

            {/* Header */}
            <div className="flex items-center gap-4 mb-8">
              <div className="w-12 h-12 rounded-xl bg-purple-500 flex items-center justify-center text-white">
                <Mic2 size={24} />
              </div>
              <div>
                <h1 className="font-[family-name:var(--font-outfit)] text-2xl font-bold">
                  팟캐스트 생성
                </h1>
                <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)]">
                  주제를 입력하고 팟캐스트 스크립트를 생성하세요
                </p>
              </div>
            </div>

            {/* Input Form */}
            {!script && !isLoading && (
              <div className="space-y-6">
                {/* Goal Input */}
                <div>
                  <label className="block font-[family-name:var(--font-dm-sans)] text-sm font-medium mb-2">
                    팟캐스트 목표 *
                  </label>
                  <textarea
                    value={goal}
                    onChange={(e) => setGoal(e.target.value)}
                    placeholder="예: EGFR 표적 치료의 최신 동향 설명해줘"
                    className="w-full px-4 py-3 rounded-xl border-2 border-[var(--oaria-border)] bg-[var(--background)] font-[family-name:var(--font-dm-sans)] text-sm resize-none focus:outline-none focus:border-[var(--oaria-teal)] transition-colors"
                    rows={3}
                  />
                  <p className="mt-2 text-xs text-[var(--oaria-text-secondary)]">
                    명확하고 구체적인 주제를 입력하세요. 검색 가능한 암 연구 관련 주제여야 합니다.
                  </p>
                </div>

                {/* Quick Options */}
                <div className="grid grid-cols-3 gap-4">
                  {/* Duration */}
                  <div>
                    <label className="block font-[family-name:var(--font-dm-sans)] text-sm font-medium mb-2">
                      길이
                    </label>
                    <select
                      value={duration}
                      onChange={(e) => setDuration(e.target.value as typeof duration)}
                      className="w-full px-4 py-2.5 rounded-xl border-2 border-[var(--oaria-border)] bg-[var(--background)] font-[family-name:var(--font-dm-sans)] text-sm focus:outline-none focus:border-[var(--oaria-teal)] transition-colors"
                    >
                      <option value="short">짧게 (~5분)</option>
                      <option value="medium">보통 (~10분)</option>
                      <option value="long">길게 (~15분)</option>
                    </select>
                  </div>

                  {/* Style */}
                  <div>
                    <label className="block font-[family-name:var(--font-dm-sans)] text-sm font-medium mb-2">
                      스타일
                    </label>
                    <select
                      value={style}
                      onChange={(e) => setStyle(e.target.value as typeof style)}
                      className="w-full px-4 py-2.5 rounded-xl border-2 border-[var(--oaria-border)] bg-[var(--background)] font-[family-name:var(--font-dm-sans)] text-sm focus:outline-none focus:border-[var(--oaria-teal)] transition-colors"
                    >
                      <option value="two_hosts">두 호스트 대화</option>
                      <option value="interview">인터뷰</option>
                      <option value="solo">단독 발표</option>
                    </select>
                  </div>

                  {/* Language */}
                  <div>
                    <label className="block font-[family-name:var(--font-dm-sans)] text-sm font-medium mb-2">
                      언어
                    </label>
                    <select
                      value={language}
                      onChange={(e) => setLanguage(e.target.value as typeof language)}
                      className="w-full px-4 py-2.5 rounded-xl border-2 border-[var(--oaria-border)] bg-[var(--background)] font-[family-name:var(--font-dm-sans)] text-sm focus:outline-none focus:border-[var(--oaria-teal)] transition-colors"
                    >
                      <option value="ko">한국어</option>
                      <option value="en">English</option>
                    </select>
                  </div>
                </div>

                {/* Generate Button */}
                <button
                  onClick={handleGenerate}
                  disabled={!goal.trim()}
                  className="w-full px-6 py-4 rounded-xl bg-[var(--oaria-teal)] text-white font-[family-name:var(--font-dm-sans)] font-semibold hover:bg-[#0B7A70] disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                >
                  <Sparkles size={20} />
                  팟캐스트 생성하기
                </button>
              </div>
            )}

            {/* Loading State */}
            {isLoading && (
              <div className="space-y-6">
                {/* Progress Nodes */}
                <div className="p-6 rounded-xl border-2 border-[var(--oaria-border)] bg-[var(--background)]">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-[family-name:var(--font-outfit)] font-semibold">
                      생성 진행 상황
                    </h3>
                    <span className="text-sm text-[var(--oaria-text-secondary)]">
                      {formatTime(elapsedTime)}
                    </span>
                  </div>
                  <div className="space-y-3">
                    {nodes.map((node) => (
                      <div
                        key={node.id}
                        className={`flex items-center gap-3 p-3 rounded-lg transition-colors ${
                          node.status === "active"
                            ? "bg-[var(--oaria-teal)]/10"
                            : node.status === "completed"
                            ? "bg-green-500/10"
                            : ""
                        }`}
                      >
                        <div className={`flex-shrink-0 ${
                          node.status === "active"
                            ? "text-[var(--oaria-teal)]"
                            : node.status === "completed"
                            ? "text-green-500"
                            : "text-[var(--oaria-text-secondary)]"
                        }`}>
                          {node.status === "active" ? (
                            <Loader2 size={16} className="animate-spin" />
                          ) : node.status === "completed" ? (
                            <CheckCircle2 size={16} />
                          ) : (
                            <Circle size={16} />
                          )}
                        </div>
                        <div className="flex-1">
                          <p className={`font-[family-name:var(--font-dm-sans)] text-sm font-medium ${
                            node.status === "pending" ? "text-[var(--oaria-text-secondary)]" : ""
                          }`}>
                            {node.label}
                          </p>
                          <p className="font-[family-name:var(--font-dm-sans)] text-xs text-[var(--oaria-text-secondary)]">
                            {node.description}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Cancel Button */}
                <button
                  onClick={handleCancel}
                  className="w-full px-6 py-3 rounded-xl border-2 border-[var(--oaria-border-strong)] text-[var(--foreground)] font-[family-name:var(--font-dm-sans)] font-medium hover:border-red-500 hover:text-red-500 transition-colors"
                >
                  취소
                </button>
              </div>
            )}

            {/* Error State */}
            {error && !isLoading && (
              <div className="p-6 rounded-xl border-2 border-red-500/30 bg-red-500/5">
                <p className="font-[family-name:var(--font-dm-sans)] text-sm text-red-500 mb-4">
                  {error}
                </p>
                <button
                  onClick={handleReset}
                  className="px-4 py-2 rounded-lg bg-red-500 text-white text-sm font-medium hover:bg-red-600 transition-colors"
                >
                  다시 시도
                </button>
              </div>
            )}

            {/* Result - Script Display */}
            {script && !isLoading && (
              <div className="space-y-6">
                {/* Script Header */}
                <div className="p-6 rounded-xl border-2 border-[var(--oaria-teal)]/30 bg-[var(--oaria-teal)]/5">
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <h2 className="font-[family-name:var(--font-outfit)] text-xl font-bold mb-2">
                        {script.title}
                      </h2>
                      <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)]">
                        {script.description}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-[var(--oaria-text-secondary)]">
                      <Clock size={16} />
                      ~{Math.round(script.total_estimated_duration / 60)}분
                    </div>
                  </div>
                  <div className="flex items-center gap-4 text-sm">
                    <span className="px-3 py-1 rounded-full bg-purple-500/20 text-purple-500 font-medium">
                      {script.speakers.join(" & ")}
                    </span>
                    <span className="text-[var(--oaria-text-secondary)]">
                      {script.turns.length}개 대화
                    </span>
                  </div>

                  {/* Audio Player */}
                  {audioUrl && (
                    <div className="mt-4 p-4 rounded-lg bg-[var(--background)] border border-[var(--oaria-border)]">
                      <div className="flex items-center gap-3 mb-2">
                        <Mic2 size={18} className="text-[var(--oaria-teal)]" />
                        <span className="font-[family-name:var(--font-dm-sans)] text-sm font-medium">
                          팟캐스트 오디오
                        </span>
                      </div>
                      <audio
                        src={audioUrl}
                        controls
                        className="w-full h-10"
                      />
                    </div>
                  )}
                </div>

                {/* Dialogue Turns */}
                <div className="space-y-4">
                  {script.turns.map((turn, idx) => (
                    <div
                      key={idx}
                      className={`p-4 rounded-xl border-2 ${
                        turn.speaker === script.speakers[0]
                          ? "border-[var(--oaria-teal)]/30 bg-[var(--oaria-teal)]/5"
                          : "border-[var(--oaria-border)] bg-[var(--background)]"
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                          turn.speaker === script.speakers[0]
                            ? "bg-[var(--oaria-teal)] text-white"
                            : "bg-purple-500 text-white"
                        }`}>
                          {turn.speaker}
                        </span>
                        {turn.citations && turn.citations.length > 0 && (
                          <span className="text-xs text-[var(--oaria-text-secondary)]">
                            인용: [{turn.citations.join(", ")}]
                          </span>
                        )}
                      </div>
                      <p className="font-[family-name:var(--font-dm-sans)] text-sm leading-relaxed">
                        {turn.text}
                      </p>
                    </div>
                  ))}
                </div>

                {/* References */}
                {references.length > 0 && (
                  <div className="p-6 rounded-xl border-2 border-[var(--oaria-border)] bg-[var(--background)]">
                    <h3 className="font-[family-name:var(--font-outfit)] font-semibold mb-4">
                      참고 문헌
                    </h3>
                    <div className="space-y-3">
                      {references.map((ref) => (
                        <div key={ref.index} className="text-sm">
                          <span className="font-medium text-[var(--oaria-teal)]">[{ref.index}]</span>{" "}
                          <span className="font-medium">{ref.title}</span>
                          {ref.journal && (
                            <span className="text-[var(--oaria-text-secondary)]">
                              {" - "}{ref.journal}
                              {ref.year && ` (${ref.year})`}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="flex items-center gap-4">
                  <button
                    onClick={handleReset}
                    className="flex-1 px-6 py-3 rounded-xl border-2 border-[var(--oaria-border-strong)] text-[var(--foreground)] font-[family-name:var(--font-dm-sans)] font-medium hover:border-[var(--oaria-teal)] transition-colors"
                  >
                    새로 만들기
                  </button>
                  {episodeId ? (
                    <Link
                      href={`/agents/podcast/${episodeId}`}
                      className="flex-1 px-6 py-3 rounded-xl bg-[var(--oaria-teal)] text-white font-[family-name:var(--font-dm-sans)] font-medium hover:bg-[#0B7A70] transition-colors text-center"
                    >
                      에피소드 보기
                    </Link>
                  ) : (
                    <Link
                      href="/agents/podcast/history"
                      className="flex-1 px-6 py-3 rounded-xl bg-[var(--oaria-teal)] text-white font-[family-name:var(--font-dm-sans)] font-medium hover:bg-[#0B7A70] transition-colors text-center"
                    >
                      기록 보기
                    </Link>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Activity Sidebar */}
        {showActivitySidebar && (isLoading || activityLogs.length > 0) && (
          <div className="w-80 border-l-2 border-[var(--oaria-border)] bg-[var(--background)] flex flex-col">
            <div className="p-4 border-b-2 border-[var(--oaria-border)] flex items-center justify-between">
              <h3 className="font-[family-name:var(--font-outfit)] font-semibold">
                활동 로그
              </h3>
              <button
                onClick={() => setShowActivitySidebar(false)}
                className="p-1.5 rounded-lg hover:bg-[var(--oaria-border)]/50 transition-colors"
              >
                <X size={16} />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              <div className="space-y-3">
                {activityLogs.map((log) => (
                  <div
                    key={log.id}
                    className={`p-3 rounded-lg text-sm ${
                      log.type === "error"
                        ? "bg-red-500/10 border border-red-500/30"
                        : log.type === "result"
                        ? "bg-green-500/10 border border-green-500/30"
                        : log.type === "action"
                        ? "bg-[var(--oaria-teal)]/10 border border-[var(--oaria-teal)]/30"
                        : "bg-[var(--oaria-border)]/30"
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      {log.type === "thinking" && <Brain size={14} className="text-[var(--oaria-text-secondary)]" />}
                      {log.type === "action" && <Target size={14} className="text-[var(--oaria-teal)]" />}
                      {log.type === "result" && <CheckCircle2 size={14} className="text-green-500" />}
                      {log.type === "error" && <X size={14} className="text-red-500" />}
                      <span className="font-medium">{log.title}</span>
                    </div>
                    {log.description && (
                      <p className="text-xs text-[var(--oaria-text-secondary)] ml-5">
                        {log.description}
                      </p>
                    )}
                    <p className="text-xs text-[var(--oaria-text-secondary)] ml-5 mt-1">
                      {log.timestamp.toLocaleTimeString()}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

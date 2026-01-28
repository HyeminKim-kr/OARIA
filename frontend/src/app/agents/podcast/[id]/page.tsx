"use client";

import { useState, useEffect, useRef, useMemo, use } from "react";
import Link from "next/link";
import {
  Search,
  Bot,
  MessageSquare,
  BarChart3,
  Loader2,
  ArrowLeft,
  Mic2,
  Clock,
  Calendar,
  FileText,
  Play,
  Volume2,
  Users,
  AlertCircle,
  CheckCircle2,
} from "lucide-react";
import { podcastApi, PodcastEpisode, PodcastDialogueScript, PodcastReference, TurnTiming } from "@/lib/api";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function PodcastEpisodeDetailPage({ params }: PageProps) {
  const resolvedParams = use(params);
  const [episode, setEpisode] = useState<PodcastEpisode | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [activeTurnIndex, setActiveTurnIndex] = useState<number | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Fetch episode
  useEffect(() => {
    const fetchEpisode = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await podcastApi.get(resolvedParams.id);
        setEpisode(response.data);
      } catch (err) {
        console.error("Failed to fetch episode:", err);
        setError("에피소드를 불러오는 중 오류가 발생했습니다.");
      } finally {
        setIsLoading(false);
      }
    };

    fetchEpisode();
  }, [resolvedParams.id]);

  // Extract turn_timings from episode data (may be in top-level or nested in script JSONB)
  const turnTimings: TurnTiming[] = useMemo(() =>
    episode?.turn_timings
    || episode?.script?.turn_timings
    || (episode?.script as unknown as Record<string, TurnTiming[]> | null)?.turn_timings
    || [],
    [episode],
  );

  // Auto-scroll to active turn when it changes
  useEffect(() => {
    if (activeTurnIndex !== null) {
      const el = document.getElementById(`turn-${activeTurnIndex}`);
      el?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [activeTurnIndex]);

  // Audio timeupdate handler (called via onTimeUpdate prop, no listener timing issues)
  const handleAudioTimeUpdate = (e: React.SyntheticEvent<HTMLAudioElement>) => {
    if (turnTimings.length === 0) return;
    const currentTime = e.currentTarget.currentTime;
    let foundIndex: number | null = null;
    for (const tt of turnTimings) {
      if (currentTime >= tt.start_time && currentTime < tt.end_time) {
        foundIndex = tt.turn_index;
        break;
      }
    }
    setActiveTurnIndex((prev) => (prev !== foundIndex ? foundIndex : prev));
  };

  // Format date
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString("ko-KR", {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  // Format duration
  const formatDuration = (seconds: number | null) => {
    if (!seconds) return "-";
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}분 ${secs}초`;
  };

  // Get style label
  const getStyleLabel = (style: string) => {
    switch (style) {
      case "two_hosts":
        return "두 호스트 대화";
      case "interview":
        return "인터뷰";
      case "solo":
        return "단독 발표";
      default:
        return style;
    }
  };

  // Get status info
  const getStatusInfo = (status: string) => {
    switch (status) {
      case "completed":
        return {
          icon: <CheckCircle2 size={16} className="text-green-500" />,
          label: "완료",
          className: "bg-green-500/20 text-green-500",
        };
      case "generating":
      case "pending":
        return {
          icon: <Loader2 size={16} className="animate-spin text-yellow-500" />,
          label: "생성 중",
          className: "bg-yellow-500/20 text-yellow-500",
        };
      case "failed":
        return {
          icon: <AlertCircle size={16} className="text-red-500" />,
          label: "실패",
          className: "bg-red-500/20 text-red-500",
        };
      default:
        return {
          icon: null,
          label: status,
          className: "bg-[var(--oaria-border)] text-[var(--oaria-text-secondary)]",
        };
    }
  };

  const script = episode?.script as PodcastDialogueScript | null;
  const references = episode?.references as PodcastReference[] | null;

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Navigation Tabs */}
      <div className="bg-[var(--background)]">
        <div className="flex items-center justify-center">
          <div className="flex items-center gap-6">
            <Link
              href="/ask"
              className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-colors"
            >
              <MessageSquare size={20} />
              Ask AI
            </Link>
            <Link
              href="/main"
              className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-colors"
            >
              <Search size={20} />
              Search Papers
            </Link>
            <Link
              href="/agents"
              className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-[var(--oaria-teal)] text-[var(--oaria-teal)]"
            >
              <Bot size={20} />
              Agents
            </Link>
            <Link
              href="/dashboard"
              className="flex items-center gap-2 px-4 py-3 font-[family-name:var(--font-dm-sans)] text-base font-medium border-b-2 border-transparent text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] transition-colors"
            >
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
          <Link
            href="/agents/podcast/history"
            className="inline-flex items-center gap-2 text-sm text-[var(--oaria-text-secondary)] hover:text-[var(--foreground)] mb-6 transition-colors"
          >
            <ArrowLeft size={16} />
            에피소드 목록
          </Link>

          {/* Loading State */}
          {isLoading && (
            <div className="flex items-center justify-center py-20">
              <Loader2 size={32} className="animate-spin text-[var(--oaria-teal)]" />
            </div>
          )}

          {/* Error State */}
          {error && !isLoading && (
            <div className="p-6 rounded-xl border-2 border-red-500/30 bg-red-500/5 text-center">
              <AlertCircle size={32} className="mx-auto mb-3 text-red-500" />
              <p className="font-[family-name:var(--font-dm-sans)] text-sm text-red-500">
                {error}
              </p>
            </div>
          )}

          {/* Episode Content */}
          {!isLoading && !error && episode && (
            <div className="space-y-6">
              {/* Header */}
              <div className="p-6 rounded-xl border-2 border-[var(--oaria-teal)]/30 bg-[var(--oaria-teal)]/5">
                <div className="flex items-start gap-4 mb-4">
                  <div className="w-14 h-14 rounded-xl bg-[var(--oaria-coral)] flex items-center justify-center text-white flex-shrink-0">
                    <Mic2 size={28} />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      {(() => {
                        const status = getStatusInfo(episode.status);
                        return (
                          <span className={`px-2 py-0.5 rounded-full text-xs font-medium flex items-center gap-1 ${status.className}`}>
                            {status.icon}
                            {status.label}
                          </span>
                        );
                      })()}
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-[var(--oaria-coral)]/20 text-[var(--oaria-coral)]">
                        {getStyleLabel(episode.style)}
                      </span>
                    </div>
                    <h1 className="font-[family-name:var(--font-outfit)] text-2xl font-bold mb-2">
                      {script?.title || episode.title || episode.goal}
                    </h1>
                    <p className="font-[family-name:var(--font-dm-sans)] text-sm text-[var(--oaria-text-secondary)]">
                      {script?.description || episode.description || episode.goal}
                    </p>
                  </div>
                </div>

                {/* Metadata */}
                <div className="flex flex-wrap items-center gap-4 text-sm text-[var(--oaria-text-secondary)]">
                  <span className="flex items-center gap-1.5">
                    <Calendar size={14} />
                    {formatDate(episode.created_at)}
                  </span>
                  {episode.duration_seconds && (
                    <span className="flex items-center gap-1.5">
                      <Clock size={14} />
                      {formatDuration(episode.duration_seconds)}
                    </span>
                  )}
                  {script?.speakers && (
                    <span className="flex items-center gap-1.5">
                      <Users size={14} />
                      {script.speakers.join(" & ")}
                    </span>
                  )}
                  {episode.paper_ids && episode.paper_ids.length > 0 && (
                    <span className="flex items-center gap-1.5">
                      <FileText size={14} />
                      {episode.paper_ids.length}개 논문 참조
                    </span>
                  )}
                </div>

                {/* Audio Player */}
                {episode.audio_url && (
                  <div className="mt-4 p-4 rounded-lg bg-[var(--background)] border border-[var(--oaria-border)]">
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => {
                          const audio = audioRef.current;
                          if (!audio) return;
                          if (isPlaying) {
                            audio.pause();
                          } else {
                            audio.play();
                          }
                        }}
                        className="w-12 h-12 rounded-full bg-[var(--oaria-teal)] text-white flex items-center justify-center hover:bg-[#0B7A70] transition-colors"
                      >
                        {isPlaying ? <Volume2 size={20} /> : <Play size={20} className="ml-0.5" />}
                      </button>
                      <div className="flex-1">
                        <audio
                          ref={audioRef}
                          src={episode.audio_url}
                          controls
                          className="w-full h-10"
                          onPlay={() => setIsPlaying(true)}
                          onPause={() => setIsPlaying(false)}
                          onTimeUpdate={handleAudioTimeUpdate}
                          onEnded={() => setActiveTurnIndex(null)}
                        />
                        {turnTimings.length > 0 && (
                          <p className="text-xs text-[var(--oaria-text-secondary)] mt-1">
                            대화를 클릭하면 해당 위치로 이동합니다
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Script */}
              {script && script.turns && script.turns.length > 0 && (
                <div className="space-y-4">
                  <h2 className="font-[family-name:var(--font-outfit)] text-lg font-semibold">
                    스크립트
                  </h2>
                  <div className="space-y-3">
                    {script.turns.map((turn, idx) => {
                      const isActive = activeTurnIndex === idx;
                      const hasTiming = turnTimings.some(tt => tt.turn_index === idx);
                      return (
                        <div
                          key={idx}
                          id={`turn-${idx}`}
                          onClick={() => {
                            if (!hasTiming || !audioRef.current) return;
                            const timing = turnTimings.find(tt => tt.turn_index === idx);
                            if (timing) {
                              audioRef.current.currentTime = timing.start_time;
                              audioRef.current.play();
                            }
                          }}
                          className={`p-4 rounded-xl border-2 transition-all duration-300 ${
                            isActive
                              ? "border-[var(--oaria-teal)] bg-[var(--oaria-teal)]/15 ring-2 ring-[var(--oaria-teal)]/40 shadow-lg shadow-[var(--oaria-teal)]/10"
                              : turn.speaker === script.speakers[0]
                              ? "border-[var(--oaria-teal)]/30 bg-[var(--oaria-teal)]/5"
                              : "border-[var(--oaria-border)] bg-[var(--background)]"
                          } ${hasTiming ? "cursor-pointer hover:border-[var(--oaria-teal)]/60" : ""}`}
                        >
                          <div className="flex items-center gap-2 mb-2">
                            {isActive && (
                              <Volume2 size={14} className="text-[var(--oaria-teal)] animate-pulse" />
                            )}
                            <span
                              className={`px-2 py-0.5 rounded text-xs font-semibold ${
                                turn.speaker === script.speakers[0]
                                  ? "bg-[var(--oaria-teal)] text-white"
                                  : "bg-[var(--oaria-coral)] text-white"
                              }`}
                            >
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
                      );
                    })}
                  </div>
                </div>
              )}

              {/* References */}
              {references && references.length > 0 && (
                <div className="p-6 rounded-xl border-2 border-[var(--oaria-border)] bg-[var(--background)]">
                  <h2 className="font-[family-name:var(--font-outfit)] text-lg font-semibold mb-4">
                    참고 문헌
                  </h2>
                  <div className="space-y-4">
                    {references.map((ref) => (
                      <div key={ref.index} className="text-sm">
                        <div className="flex items-start gap-2 mb-1">
                          <span className="font-semibold text-[var(--oaria-teal)] flex-shrink-0">
                            [{ref.index}]
                          </span>
                          <div className="flex-1">
                            <p className="font-medium">{ref.title}</p>
                            {ref.authors && ref.authors.length > 0 && (
                              <p className="text-[var(--oaria-text-secondary)] text-xs mt-0.5">
                                {ref.authors.slice(0, 3).join(", ")}
                                {ref.authors.length > 3 && " 외"}
                              </p>
                            )}
                            <p className="text-[var(--oaria-text-secondary)] text-xs">
                              {ref.journal}
                              {ref.year && ` (${ref.year})`}
                            </p>
                            {ref.snippet && (
                              <p className="text-xs text-[var(--oaria-text-secondary)] mt-2 p-2 rounded bg-[var(--oaria-border)]/30 italic">
                                &ldquo;{ref.snippet}&rdquo;
                              </p>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Error Message */}
              {episode.error_message && (
                <div className="p-4 rounded-xl border-2 border-red-500/30 bg-red-500/5">
                  <div className="flex items-start gap-2">
                    <AlertCircle size={18} className="text-red-500 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-[family-name:var(--font-dm-sans)] font-medium text-red-500 mb-1">
                        오류 발생
                      </p>
                      <p className="font-[family-name:var(--font-dm-sans)] text-sm text-red-500/80">
                        {episode.error_message}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex items-center gap-4 pt-4">
                <Link
                  href="/agents/podcast"
                  className="flex-1 px-6 py-3 rounded-xl bg-[var(--oaria-teal)] text-white font-[family-name:var(--font-dm-sans)] font-medium hover:bg-[#0B7A70] transition-colors text-center"
                >
                  새 에피소드 만들기
                </Link>
                <Link
                  href="/agents/podcast/history"
                  className="flex-1 px-6 py-3 rounded-xl border-2 border-[var(--oaria-border-strong)] text-[var(--foreground)] font-[family-name:var(--font-dm-sans)] font-medium hover:border-[var(--oaria-teal)] transition-colors text-center"
                >
                  목록으로
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

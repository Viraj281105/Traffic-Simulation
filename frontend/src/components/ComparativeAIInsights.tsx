import React, { useCallback, useEffect, useRef, useState } from "react";
import { Send, Bot, RefreshCw, AlertTriangle } from "lucide-react";
import type { DualSnapshot } from "../types/simulation";
import {
  fetchSummary,
  fetchChat,
  type SummaryResponse,
  type ConversationTurn,
} from "../services/copilotApi";
import "./ComparativeAIInsights.css";

interface ComparativeAIInsightsProps {
  snapshot: DualSnapshot | null;
  replayName?: string | null;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  fallback?: boolean;
}

export const ComparativeAIInsights: React.FC<ComparativeAIInsightsProps> = ({
  snapshot,
  replayName,
}) => {
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [loadingChat, setLoadingChat] = useState(false);

  const chatBottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const hasTriggeredRef = useRef(false);

  const signalMetrics = (snapshot?.signal?.metrics ?? {}) as Record<string, any>;
  const roundaboutMetrics = (snapshot?.roundabout?.metrics ?? {}) as Record<string, any>;
  const elapsed = snapshot?.signal?.timestamp ?? null;

  const comparativePayload = {
    signal: signalMetrics,
    roundabout: roundaboutMetrics,
    comparison: {
      delayDelta_roundaboutMinusSignal:
        signalMetrics.averageDelay != null && roundaboutMetrics.averageDelay != null
          ? Number((roundaboutMetrics.averageDelay - signalMetrics.averageDelay).toFixed(2))
          : null,
      throughputDelta_roundaboutMinusSignal:
        signalMetrics.throughput != null && roundaboutMetrics.throughput != null
          ? Number((roundaboutMetrics.throughput - signalMetrics.throughput).toFixed(0))
          : null,
      maxQueueDelta_roundaboutMinusSignal:
        signalMetrics.maxQueueLength != null && roundaboutMetrics.maxQueueLength != null
          ? Number((roundaboutMetrics.maxQueueLength - signalMetrics.maxQueueLength).toFixed(0))
          : null,
      fairnessDelta_roundaboutMinusSignal:
        signalMetrics.directionalFairnessIndex != null && roundaboutMetrics.directionalFairnessIndex != null
          ? Number((roundaboutMetrics.directionalFairnessIndex - signalMetrics.directionalFairnessIndex).toFixed(3))
          : null,
    },
    context: {
      replayName: replayName ?? null,
      elapsedSeconds: elapsed,
    },
  };

  const generateSummary = useCallback(async () => {
    if (!snapshot?.signal?.metrics && !snapshot?.roundabout?.metrics) return;
    setLoadingSummary(true);
    setSummaryError(null);
    try {
      const res = await fetchSummary({
        metrics: comparativePayload as unknown as Record<string, unknown>,
        config: {},
        geometry: "comparison",
        elapsed_seconds: elapsed,
      });
      setSummary(res);
    } catch (err: unknown) {
      setSummaryError(
        err instanceof Error ? err.message : "Failed to generate comparison insights."
      );
    } finally {
      setLoadingSummary(false);
    }
  }, [snapshot, elapsed]);

  // Auto-generate as soon as results/data exist
  useEffect(() => {
    const hasData =
      snapshot?.signal?.metrics?.throughput != null ||
      snapshot?.roundabout?.metrics?.throughput != null ||
      snapshot?.signal?.metrics?.averageDelay != null ||
      snapshot?.roundabout?.metrics?.averageDelay != null;

    if (hasData && !hasTriggeredRef.current) {
      hasTriggeredRef.current = true;
      void generateSummary();
    }
  }, [snapshot, generateSummary]);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  const handleSendChat = async () => {
    const q = draft.trim();
    if (!q || loadingChat) return;
    const userMsg: ChatMessage = { role: "user", content: q };
    setChatMessages((prev) => [...prev, userMsg]);
    setDraft("");
    const history: ConversationTurn[] = chatMessages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    try {
      const res = await fetchChat({
        question: q,
        metrics: comparativePayload as unknown as Record<string, unknown>,
        config: {},
        geometry: "comparison",
        history,
      });
      setChatMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.answer, fallback: res.fallback },
      ]);
    } catch (err: unknown) {
      const errorMsg =
        err instanceof Error ? err.message : "Failed to get AI answer.";
      setChatMessages((prev) => [
        ...prev,
        { role: "assistant", content: errorMsg, fallback: true },
      ]);
    } finally {
      setLoadingChat(false);
      setTimeout(() => textareaRef.current?.focus(), 60);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSendChat();
    }
  };

  return (
    <div className="comparative-ai-container">
      {/* Executive Summary Card */}
      <div className="modal-section-card ai-summary-section">
        <div className="ai-summary-header">
          <div className="ai-badge-row">
            <span className="ai-section-tag">AI ANALYSIS</span>
            <h3 className="modal-section-title">Automated Comparison Summary & Insights</h3>
          </div>
          <button
            type="button"
            className="ai-refresh-btn"
            onClick={() => void generateSummary()}
            disabled={loadingSummary}
            title="Refresh AI Analysis"
          >
            <RefreshCw size={13} className={loadingSummary ? "ai-spin" : ""} />
            <span>{loadingSummary ? "Analyzing…" : "Regenerate"}</span>
          </button>
        </div>

        {loadingSummary && !summary && (
          <div className="ai-loading-box">
            <div className="ai-spinner-circle" />
            <p>Analyzing signal vs roundabout telemetry metrics…</p>
          </div>
        )}

        {summaryError && !loadingSummary && (
          <div className="ai-alert-banner">
            <AlertTriangle size={15} />
            <span>{summaryError}</span>
          </div>
        )}

        {summary && (
          <div className="ai-summary-content">
            <div className="ai-lead-summary">
              <strong>Executive Takeaway:</strong> {summary.summary}
            </div>

            {summary.bullets.length > 0 && (
              <div className="ai-insights-grid">
                {summary.bullets.map((b: string, i: number) => (
                  <div key={i} className="ai-insight-item">
                    <span className="ai-item-dot" />
                    <span>{b}</span>
                  </div>
                ))}
              </div>
            )}

            {summary.warnings.length > 0 && (
              <div className="ai-warnings-list">
                {summary.warnings.map((w: string, i: number) => (
                  <div key={i} className="ai-warning-pill">
                    <AlertTriangle size={13} />
                    <span>{w}</span>
                  </div>
                ))}
              </div>
            )}

            {summary.fallback && (
              <div className="ai-fallback-notice">
                <span>Deterministic rule-based metrics synthesis (API key unavailable or offline).</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Interactive Q&A Card */}
      <div className="modal-section-card ai-chat-section">
        <div className="ai-chat-header">
          <div>
            <h3 className="modal-section-title">Comparative Q&A Analyst</h3>
            <p className="ai-section-subtitle">
              Ask deep questions about this comparison (e.g. "Which junction handles queue clearance better?", "Is the difference in delay statistically significant?", "Where did delays spike?").
            </p>
          </div>
        </div>

        <div className="ai-chat-thread">
          {chatMessages.length === 0 ? (
            <div className="ai-chat-empty">
              <Bot size={28} className="ai-empty-icon" />
              <p>Ask any analytical questions comparing signal and roundabout performance for this run.</p>
              <div className="ai-suggested-prompts">
                <button
                  type="button"
                  className="ai-suggestion-chip"
                  onClick={() => {
                    setDraft("Which intersection provided better throughput and why?");
                  }}
                >
                  Which intersection provided better throughput and why?
                </button>
                <button
                  type="button"
                  className="ai-suggestion-chip"
                  onClick={() => {
                    setDraft("How did average delay and max queue length compare?");
                  }}
                >
                  How did average delay and max queue length compare?
                </button>
                <button
                  type="button"
                  className="ai-suggestion-chip"
                  onClick={() => {
                    setDraft("Which design maintained better directional fairness?");
                  }}
                >
                  Which design maintained better directional fairness?
                </button>
              </div>
            </div>
          ) : (
            <div className="ai-messages-list">
              {chatMessages.map((msg, i) => (
                <div key={i} className={`ai-message-row ${msg.role}`}>
                  <div className="ai-message-bubble">
                    <div className="ai-message-text">{msg.content}</div>
                    {msg.fallback && (
                      <span className="ai-message-tag">Rule-based answer</span>
                    )}
                  </div>
                </div>
              ))}
              {loadingChat && (
                <div className="ai-message-row assistant">
                  <div className="ai-message-bubble ai-typing-indicator">
                    <span />
                    <span />
                    <span />
                  </div>
                </div>
              )}
              <div ref={chatBottomRef} />
            </div>
          )}
        </div>

        <div className="ai-chat-input-bar">
          <textarea
            ref={textareaRef}
            rows={1}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about these comparison metrics… (Enter to send)"
            disabled={loadingChat}
            className="ai-chat-textarea"
          />
          <button
            type="button"
            className="ai-chat-send-btn"
            onClick={() => void handleSendChat()}
            disabled={loadingChat || !draft.trim()}
            aria-label="Send query"
          >
            <Send size={15} />
          </button>
        </div>
      </div>
    </div>
  );
};

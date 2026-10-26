import React, {
  useCallback,
  useEffect,
  useRef,
  useState,
  useMemo,
} from "react";
import {
  Bot,
  X,
  Send,
  RotateCcw,
  Sparkles,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import type { ViewMode } from "../shell/sections";
import type { LiveSnapshot, DualSnapshot } from "../../types/simulation";
import type { SimulationConfigValues } from "../../types/config";
import {
  fetchChat,
  type ConversationTurn,
  type CopilotGeometry,
} from "../../services/copilotApi";
import "./FloatingAICopilot.css";

export interface FloatingAICopilotProps {
  viewMode: ViewMode;
  snapshot?: LiveSnapshot | null;
  dualSnapshot?: DualSnapshot | null;
  config?: SimulationConfigValues | null;
  replayName?: string | null;
}

interface InternalChatMessage {
  role: "user" | "assistant";
  content: string;
  fallback?: boolean;
}

interface ContextInfo {
  label: string;
  tag: string;
  description: string;
  geometry: CopilotGeometry;
  suggestedQuestions: string[];
}

export const FloatingAICopilot: React.FC<FloatingAICopilotProps> = ({
  viewMode,
  snapshot,
  dualSnapshot,
  config,
  replayName,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [messages, setMessages] = useState<InternalChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const chatBottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Determine current page context & dynamic questions
  const contextInfo: ContextInfo = useMemo(() => {
    switch (viewMode) {
      case "research":
      case "threeWay":
      case "junction":
        return {
          label: "Research Lab",
          tag: "Research",
          description:
            "Analyzing multi-strategy benchmarks, matched seed evaluations, and empirical evidence.",
          geometry: "research",
          suggestedQuestions: [
            "Which traffic-control strategy performed better?",
            "What do these results tell us about signals versus roundabouts?",
            "What are the key findings from my experiments?",
            "Explain the evidence ladder for traffic control validation.",
          ],
        };

      case "validation":
        return {
          label: "Statistical Validation",
          tag: "Monte Carlo",
          description:
            "Inspecting Monte Carlo significance tests, p-values, and paired seed variance.",
          geometry: "research",
          suggestedQuestions: [
            "Are the delay differences statistically significant?",
            "Why do we evaluate performance across paired random seeds?",
            "How does variance change under heavy traffic demand?",
          ],
        };

      case "volume":
        return {
          label: "Traffic-Level Sweep",
          tag: "Sweep",
          description:
            "Examining capacity curves, saturation breakpoints, and volume scaling.",
          geometry: "research",
          suggestedQuestions: [
            "At what volume scale does the roundabout reach capacity?",
            "Why did the average waiting time increase in heavy traffic?",
            "How do signals and roundabouts trade off at low vs high demand?",
          ],
        };

      case "planner":
        return {
          label: "Scenario Planning",
          tag: "What-If",
          description:
            "Evaluating what-if interventions, phase adjustments, and alternative scenarios.",
          geometry: "planning",
          suggestedQuestions: [
            "Which scenario experienced the longest queues?",
            "Why did average waiting time increase with the intervention?",
            "Which traffic-control strategy performed better overall?",
            "What trade-offs exist between throughput and delay here?",
          ],
        };

      case "comparative":
        return {
          label: "Comparative Evaluation",
          tag: "Compare",
          description:
            "Side-by-side comparison of Traffic Signal vs Modern Roundabout.",
          geometry: "comparison",
          suggestedQuestions: [
            "What do these results tell us about signals versus roundabouts?",
            "Which traffic-control strategy performed better?",
            "Why did the average waiting time increase in heavy traffic?",
            "Explain directional fairness index between both approaches.",
          ],
        };

      case "signal":
        return {
          label: "Traffic Signal Simulation",
          tag: "Signal",
          description:
            "Single-control signal dynamics: phase splits, queues, and vehicle discharge.",
          geometry: "fixed_time_signal",
          suggestedQuestions: [
            "Why did the average waiting time increase?",
            "Which approach has the longest queue length?",
            "Is the green duration sufficient for current arrival rates?",
          ],
        };

      case "roundabout":
        return {
          label: "Roundabout Simulation",
          tag: "Roundabout",
          description:
            "Yield-at-entry dynamics, circulating gaps, and entry queue discharge.",
          geometry: "roundabout",
          suggestedQuestions: [
            "How does critical gap affect entry queue build-up?",
            "Why did vehicles experience delays at the yield line?",
            "Is the roundabout circulating flow reaching saturation?",
          ],
        };

      default:
        return {
          label: "UrbanFlow Copilot",
          tag: "Assistant",
          description:
            "Traffic simulation assistant ready to analyze metrics and answer research questions.",
          geometry: "research",
          suggestedQuestions: [
            "Which traffic-control strategy performed better?",
            "What are the key findings from my experiments?",
            "Explain the difference between delay and waiting time.",
          ],
        };
    }
  }, [viewMode]);

  // Build the live context payload from available screen data
  const metricsPayload = useMemo(() => {
    if (viewMode === "comparative" && dualSnapshot) {
      const sig = (dualSnapshot.signal?.metrics ?? {}) as unknown as Record<string, unknown>;
      const rnd = (dualSnapshot.roundabout?.metrics ?? {}) as unknown as Record<string, unknown>;
      return {
        signal: sig,
        roundabout: rnd,
        context: {
          replayName: replayName ?? null,
          elapsedSeconds: dualSnapshot.signal?.timestamp ?? null,
        },
      };
    }
    if (snapshot?.metrics) {
      return {
        ...snapshot.metrics,
        context: {
          timestamp: snapshot.timestamp,
          controller: snapshot.controller,
        },
      };
    }
    return {};
  }, [viewMode, dualSnapshot, snapshot, replayName]);

  // Scroll to bottom on new messages
  useEffect(() => {
    if (isOpen && !isMinimized) {
      if (typeof chatBottomRef.current?.scrollIntoView === "function") {
        chatBottomRef.current.scrollIntoView({ behavior: "smooth" });
      }
    }
  }, [messages, isOpen, isMinimized]);

  // Focus textarea when popup opens
  useEffect(() => {
    if (isOpen && !isMinimized) {
      setTimeout(() => {
        textareaRef.current?.focus();
      }, 100);
    }
  }, [isOpen, isMinimized]);

  const handleSendMessage = useCallback(
    async (textToSend?: string) => {
      const question = (textToSend ?? input).trim();
      if (!question || loading) return;

      const userMsg: InternalChatMessage = { role: "user", content: question };
      setMessages((prev) => [...prev, userMsg]);
      setInput("");
      setLoading(true);

      const history: ConversationTurn[] = messages.slice(-8).map((m) => ({
        role: m.role,
        content: m.content,
      }));

      try {
        const resp = await fetchChat({
          question,
          metrics: metricsPayload as Record<string, unknown>,
          config: (config ?? {}) as Record<string, unknown>,
          geometry: contextInfo.geometry,
          history,
        });

        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: resp.answer, fallback: resp.fallback },
        ]);
      } catch (err: unknown) {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content:
              err instanceof Error
                ? `Error: ${err.message}`
                : "Unable to contact the AI Copilot service. Please try again.",
            fallback: true,
          },
        ]);
      } finally {
        setLoading(false);
      }
    },
    [input, loading, messages, metricsPayload, config, contextInfo.geometry],
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSendMessage();
    }
  };

  const handleResetConversation = () => {
    setMessages([]);
  };

  // Render quick metric summary pills if available
  const activeMetricsList = useMemo(() => {
    if (viewMode === "comparative" && dualSnapshot?.signal?.metrics) {
      const sDel = dualSnapshot.signal.metrics.averageDelay;
      const rDel = dualSnapshot.roundabout?.metrics?.averageDelay;
      const sTp = dualSnapshot.signal.metrics.throughput;
      const rTp = dualSnapshot.roundabout?.metrics?.throughput;
      const chips: Array<{ label: string; value: string }> = [];
      if (sDel != null && rDel != null) {
        chips.push({
          label: "Avg Delay",
          value: `Sig ${sDel.toFixed(1)}s / Rnd ${rDel.toFixed(1)}s`,
        });
      }
      if (sTp != null && rTp != null) {
        chips.push({
          label: "Throughput",
          value: `Sig ${String(sTp)} / Rnd ${String(rTp)}`,
        });
      }
      return chips;
    }
    if (snapshot?.metrics) {
      const chips: Array<{ label: string; value: string }> = [];
      if (snapshot.metrics.averageDelay != null) {
        chips.push({
          label: "Avg Delay",
          value: `${snapshot.metrics.averageDelay.toFixed(1)} s`,
        });
      }
      if (snapshot.metrics.throughput != null) {
        chips.push({
          label: "Throughput",
          value: `${String(snapshot.metrics.throughput)} veh`,
        });
      }
      if (snapshot.metrics.maxQueueLength != null) {
        chips.push({
          label: "Max Queue",
          value: `${String(snapshot.metrics.maxQueueLength)} veh`,
        });
      }
      return chips;
    }
    return [];
  }, [viewMode, dualSnapshot, snapshot]);

  return (
    <>
      {/* Floating Trigger Icon */}
      <button
        type="button"
        className={`floating-ai-trigger${isOpen ? " is-active" : ""}`}
        onClick={() => {
          setIsOpen((prev) => !prev);
          setIsMinimized(false);
        }}
        aria-label="Open UrbanFlow AI Research Copilot"
        title="Open UrbanFlow AI Copilot"
      >
        <span className="floating-ai-icon-wrap" aria-hidden="true">
          <span className="floating-ai-pulse" />
          <Bot size={18} />
        </span>
        <span>AI Copilot</span>
        <span className="floating-ai-context-tag">{contextInfo.tag}</span>
      </button>

      {/* Floating Contextual Popup */}
      {isOpen && (
        <div
          className="floating-ai-popup"
          role="dialog"
          aria-label="UrbanFlow AI Copilot"
          style={isMinimized ? { height: "auto" } : undefined}
        >
          {/* Header */}
          <div className="floating-ai-header">
            <div className="floating-ai-title-group">
              <div className="floating-ai-title-avatar" aria-hidden="true">
                <Sparkles size={16} />
              </div>
              <div className="floating-ai-title-text">
                <h3>UrbanFlow Copilot</h3>
                <div className="floating-ai-subtitle">
                  <span>Context:</span>
                  <span className="floating-ai-context-indicator">
                    {contextInfo.label}
                  </span>
                </div>
              </div>
            </div>

            <div className="floating-ai-actions">
              <button
                type="button"
                className="floating-ai-btn-icon"
                onClick={handleResetConversation}
                title="Restart conversation"
                aria-label="Restart conversation"
              >
                <RotateCcw size={14} aria-hidden="true" />
              </button>
              <button
                type="button"
                className="floating-ai-btn-icon"
                onClick={() => {
                  setIsMinimized((prev) => !prev);
                }}
                title={isMinimized ? "Expand popup" : "Minimize popup"}
                aria-label={isMinimized ? "Expand popup" : "Minimize popup"}
              >
                {isMinimized ? (
                  <ChevronUp size={16} aria-hidden="true" />
                ) : (
                  <ChevronDown size={16} aria-hidden="true" />
                )}
              </button>
              <button
                type="button"
                className="floating-ai-btn-icon"
                onClick={() => {
                  setIsOpen(false);
                }}
                title="Close AI Assistant"
                aria-label="Close AI Assistant"
              >
                <X size={16} aria-hidden="true" />
              </button>
            </div>
          </div>

          {/* Body */}
          {!isMinimized && (
            <>
              <div className="floating-ai-body">
                {/* Context banner */}
                <div className="floating-ai-welcome-card">
                  <p>{contextInfo.description}</p>
                  {activeMetricsList.length > 0 && (
                    <div className="floating-ai-data-summary">
                      {activeMetricsList.map((chip) => (
                        <span key={chip.label} className="floating-ai-data-chip">
                          {chip.label}: <strong>{chip.value}</strong>
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Suggested Questions */}
                {messages.length === 0 && (
                  <div className="floating-ai-suggestions">
                    <span className="floating-ai-suggestions-title">
                      Suggested Questions
                    </span>
                    {contextInfo.suggestedQuestions.map((q) => (
                      <button
                        key={q}
                        type="button"
                        className="floating-ai-pill-btn"
                        onClick={() => {
                          void handleSendMessage(q);
                        }}
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                )}

                {/* Chat Messages */}
                {messages.map((m, idx) => (
                  <div
                    key={`${m.role}-${String(idx)}`}
                    className={`floating-ai-msg is-${m.role}`}
                  >
                    <div className="floating-ai-bubble">
                      {m.content}
                      {m.fallback && (
                        <div className="floating-ai-fallback-badge">
                          (Direct simulation analysis)
                        </div>
                      )}
                    </div>
                  </div>
                ))}

                {/* Loading indicator */}
                {loading && (
                  <div className="floating-ai-msg is-assistant">
                    <div className="floating-ai-bubble floating-ai-typing">
                      <span className="floating-ai-typing-dot" />
                      <span className="floating-ai-typing-dot" />
                      <span className="floating-ai-typing-dot" />
                    </div>
                  </div>
                )}

                <div ref={chatBottomRef} />
              </div>

              {/* Footer Input Bar */}
              <div className="floating-ai-footer">
                <form
                  className="floating-ai-input-form"
                  onSubmit={(e) => {
                    e.preventDefault();
                    void handleSendMessage();
                  }}
                >
                  <textarea
                    ref={textareaRef}
                    rows={1}
                    className="floating-ai-textarea"
                    placeholder="Ask about strategies, queues, or findings…"
                    value={input}
                    onChange={(e) => {
                      setInput(e.target.value);
                    }}
                    onKeyDown={handleKeyDown}
                    disabled={loading}
                  />
                  <button
                    type="submit"
                    className="floating-ai-send-btn"
                    disabled={!input.trim() || loading}
                    aria-label="Send message"
                  >
                    <Send size={14} />
                  </button>
                </form>
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
};

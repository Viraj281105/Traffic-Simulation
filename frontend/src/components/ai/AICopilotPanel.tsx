/**
 * AICopilotPanel — the main Copilot drawer component.
 *
 * Designed to replace the MetricsSidebar on the right column while open.
 * Three tabs: Summary · Ask · Configure.
 */
import React, {
  useCallback,
  useEffect,
  useRef,
  useState,
  useId,
} from "react";
import { X, Bot, FileText, MessageCircle, Settings2, Send, BarChart2 } from "lucide-react";
import type { SimulationConfigValues } from "../../types/config";
import type { LiveSnapshot } from "../../types/simulation";
import {
  fetchSummary,
  fetchChat,
  fetchPatch,
  type SummaryResponse,
  type ChatResponse,
  type ConfigPatch,
  type ConversationTurn,
} from "../../services/copilotApi";
import "./AICopilotPanel.css";

// ── Types ──────────────────────────────────────────────────────────────────

type Tab = "summary" | "ask" | "configure";

interface Props {
  /** The current live-simulation snapshot (metrics + controller). */
  snapshot: LiveSnapshot | null;
  /** Current form values shown in ConfigurationSidebar. */
  config: SimulationConfigValues;
  /** Called with confirmed new config exactly as ConfigurationSidebar does. */
  onApply: (newConfig: SimulationConfigValues) => void;
  onClose: () => void;
  geometry: "fixed_time_signal" | "roundabout";
  /** True when a simulation is actively running (prevents silent config updates). */
  isRunning: boolean;
}

// ── Helpers ────────────────────────────────────────────────────────────────

function metricsPayload(snapshot: LiveSnapshot | null) {
  return (snapshot?.metrics ?? {}) as Record<string, unknown>;
}

function configPayload(config: SimulationConfigValues) {
  return config as unknown as Record<string, unknown>;
}

function formatKey(key: string): string {
  return key.replace(/([A-Z])/g, " $1").replace(/^./, (s) => s.toUpperCase());
}

function formatValue(val: unknown): string {
  if (typeof val === "boolean") return val ? "Yes" : "No";
  if (typeof val === "number") return val.toLocaleString(undefined, { maximumFractionDigits: 3 });
  if (val === null || val === undefined) return "—";
  if (typeof val === "object") return JSON.stringify(val);
  return String(val);
}

// ── Summary Tab ────────────────────────────────────────────────────────────

function SummaryTab({
  snapshot,
  config,
  geometry,
}: Pick<Props, "snapshot" | "config" | "geometry">) {
  const [result, setResult] = useState<SummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSummarise = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchSummary({
        metrics: metricsPayload(snapshot),
        config: configPayload(config),
        geometry,
        elapsed_seconds: snapshot?.timestamp ?? null,
      });
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to generate summary.");
    } finally {
      setLoading(false);
    }
  }, [snapshot, config, geometry]);

  const hasMetrics = snapshot?.metrics != null;

  return (
    <div className="ai-panel-body">
      {!result && !loading && (
        <>
          <p className="ai-empty-hint">
            {hasMetrics
              ? "Click below to get an AI-generated summary of the current simulation results."
              : "Start a simulation run first — the AI summarises the metrics once they are available."}
          </p>
          <button
            type="button"
            className="ai-action-btn"
            onClick={() => void handleSummarise()}
            disabled={loading || !hasMetrics}
          >
            <BarChart2 size={14} aria-hidden="true" />
            Summarize Metrics
          </button>
        </>
      )}

      {loading && (
        <div className="ai-status-row">
          <span className="ai-spinner" aria-hidden="true" />
          Generating summary…
        </div>
      )}

      {error && !loading && (
        <div className="ai-warning-item" role="alert">{error}</div>
      )}

      {result && !loading && (
        <>
          <div className="ai-summary-card">
            <p className="ai-summary-text">{result.summary}</p>
            {result.bullets.length > 0 && (
              <ul className="ai-bullets">
                {result.bullets.map((b, i) => (
                  // eslint-disable-next-line react/no-array-index-key
                  <li key={i} className="ai-bullet">{b}</li>
                ))}
              </ul>
            )}
            {result.warnings.length > 0 && (
              <div className="ai-warnings">
                {result.warnings.map((w, i) => (
                  // eslint-disable-next-line react/no-array-index-key
                  <div key={i} className="ai-warning-item">{w}</div>
                ))}
              </div>
            )}
          </div>
          {result.fallback && (
            <span className="ai-fallback-badge">
              ⚠ AI unavailable — rule-based summary
            </span>
          )}
          <button
            type="button"
            className="ai-action-btn secondary"
            onClick={() => { setResult(null); setError(null); }}
          >
            Regenerate
          </button>
        </>
      )}
    </div>
  );
}

// ── Chat Tab ───────────────────────────────────────────────────────────────

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  fallback?: boolean;
}

function ChatTab({
  snapshot,
  config,
  geometry,
}: Pick<Props, "snapshot" | "config" | "geometry">) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = useCallback(async () => {
    const q = draft.trim();
    if (!q || loading) return;
    const userMsg: ChatMessage = { role: "user", content: q };
    setMessages((prev) => [...prev, userMsg]);
    setDraft("");
    setLoading(true);
    const history: ConversationTurn[] = messages.map((m) => ({
      role: m.role,
      content: m.content,
    }));
    try {
      const res: ChatResponse = await fetchChat({
        question: q,
        metrics: metricsPayload(snapshot),
        config: configPayload(config),
        geometry,
        history,
      });
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.answer, fallback: res.fallback },
      ]);
    } catch (e: unknown) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: e instanceof Error ? e.message : "Failed to get a response.",
          fallback: true,
        },
      ]);
    } finally {
      setLoading(false);
      setTimeout(() => textareaRef.current?.focus(), 50);
    }
  }, [draft, loading, messages, snapshot, config, geometry]);

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  };

  return (
    <div className="ai-panel-body" style={{ gap: "8px" }}>
      <div className="ai-chat-history" aria-live="polite" aria-label="Conversation">
        {messages.length === 0 && (
          <p className="ai-empty-hint">
            Ask anything about this simulation — delay, queues, how the signal works, or what to try next.
          </p>
        )}
        {messages.map((m, i) => (
          // eslint-disable-next-line react/no-array-index-key
          <div key={i} className={`ai-chat-bubble ${m.role}`}>
            <div className="ai-bubble-text">{m.content}</div>
            {m.fallback && (
              <span className="ai-chat-meta">⚠ AI unavailable</span>
            )}
          </div>
        ))}
        {loading && (
          <div className="ai-chat-bubble assistant">
            <div className="ai-bubble-text ai-status-row">
              <span className="ai-spinner" aria-hidden="true" />
              Thinking…
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="ai-chat-input-row">
        <textarea
          ref={textareaRef}
          className="ai-chat-input"
          placeholder="Ask about this run… (Enter to send, Shift+Enter for new line)"
          value={draft}
          maxLength={500}
          onChange={(e) => { setDraft(e.target.value); }}
          onKeyDown={handleKey}
          aria-label="Question"
        />
        <button
          type="button"
          className="ai-send-btn"
          onClick={() => void send()}
          disabled={!draft.trim() || loading}
          aria-label="Send"
        >
          <Send size={16} aria-hidden="true" />
        </button>
      </div>

      {messages.length > 0 && (
        <button
          type="button"
          className="ai-action-btn secondary"
          style={{ fontSize: "11px", padding: "6px" }}
          onClick={() => { setMessages([]); }}
        >
          Clear conversation
        </button>
      )}
    </div>
  );
}

// ── Configure Tab ──────────────────────────────────────────────────────────

function ConfigureTab({
  config,
  geometry,
  onApply,
  isRunning,
}: Pick<Props, "config" | "geometry" | "onApply" | "isRunning">) {
  const [instruction, setInstruction] = useState("");
  const [loading, setLoading] = useState(false);
  const [patch, setPatch] = useState<ConfigPatch | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);

  const handleGenerate = useCallback(async () => {
    const instr = instruction.trim();
    if (!instr) return;
    setLoading(true);
    setError(null);
    setPatch(null);
    setConfirmed(false);
    try {
      const res = await fetchPatch({
        instruction: instr,
        current_config: configPayload(config),
        geometry,
      });
      setPatch(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to generate patch.");
    } finally {
      setLoading(false);
    }
  }, [instruction, config, geometry]);

  const handleConfirm = () => {
    if (!patch) return;
    onApply(patch.merged as unknown as SimulationConfigValues);
    setConfirmed(true);
    setPatch(null);
    setInstruction("");
  };

  const changedKeys = patch ? Object.keys(patch.patch) : [];

  return (
    <div className="ai-panel-body">
      <div className="ai-patch-form">
        <textarea
          className="ai-patch-input"
          placeholder={
            'Describe the scenario you want to simulate.\n\nExamples:\n• "Simulate heavy Pune peak-hour traffic with aggressive drivers"\n• "Try adaptive signal with light suburban traffic"\n• "Increase to 3 lanes and longer green times"'
          }
          value={instruction}
          maxLength={500}
          onChange={(e) => {
            setInstruction(e.target.value);
            setPatch(null);
            setConfirmed(false);
          }}
          aria-label="Configuration instruction"
        />
        <p className="ai-patch-hints">
          {500 - instruction.length} characters remaining. The AI will generate a before/after preview before applying anything.
        </p>
        <button
          type="button"
          className="ai-action-btn"
          onClick={() => void handleGenerate()}
          disabled={!instruction.trim() || loading}
        >
          {loading ? (
            <><span className="ai-spinner" aria-hidden="true" /> Generating patch…</>
          ) : (
            <><Settings2 size={14} aria-hidden="true" /> Preview changes</>
          )}
        </button>
      </div>

      {error && <div className="ai-warning-item" role="alert">{error}</div>}

      {confirmed && (
        <div className="ai-summary-card">
          ✅ Configuration applied. Start a new run to see the effect.
        </div>
      )}

      {isRunning && patch && (
        <div className="ai-warning-item" role="alert">
          ⚠ A simulation is running. Applying will reset the current run.
        </div>
      )}

      {patch && !confirmed && (
        <>
          {patch.clarification && (
            <div className="ai-clarification">{patch.clarification}</div>
          )}

          {changedKeys.length > 0 && (
            <div className="ai-diff-section">
              <div className="ai-diff-title">Preview — changes only</div>
              <table className="ai-diff-table">
                <thead>
                  <tr>
                    <th>Field</th>
                    <th>Before</th>
                    <th>After</th>
                  </tr>
                </thead>
                <tbody>
                  {changedKeys.map((key) => (
                    <tr key={key}>
                      <td>{formatKey(key)}</td>
                      <td className="ai-diff-before">
                        {formatValue((config as unknown as Record<string, unknown>)[key])}
                      </td>
                      <td className="ai-diff-after">
                        {formatValue(patch.patch[key])}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {patch.assumptions.length > 0 && (
            <div className="ai-diff-section">
              <div className="ai-diff-title">Assumptions</div>
              <div style={{ padding: "8px 12px" }}>
                <div className="ai-assumptions">
                  {patch.assumptions.map((a, i) => (
                    // eslint-disable-next-line react/no-array-index-key
                    <div key={i} className="ai-assumption-item">{a}</div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {patch.warnings.length > 0 && (
            <div className="ai-warnings">
              {patch.warnings.map((w, i) => (
                // eslint-disable-next-line react/no-array-index-key
                <div key={i} className="ai-warning-item">{w}</div>
              ))}
            </div>
          )}

          {patch.fallback && (
            <span className="ai-fallback-badge">⚠ AI unavailable — rule-based patch</span>
          )}

          {changedKeys.length > 0 && (
            <div className="ai-confirm-row">
              <button
                type="button"
                className="ai-action-btn"
                onClick={handleConfirm}
              >
                ✓ Apply configuration
              </button>
              <button
                type="button"
                className="ai-action-btn secondary"
                onClick={() => { setPatch(null); }}
              >
                Cancel
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Main panel ─────────────────────────────────────────────────────────────

export const AICopilotPanel: React.FC<Props> = ({
  snapshot,
  config,
  onApply,
  onClose,
  geometry,
  isRunning,
}) => {
  const [tab, setTab] = useState<Tab>("summary");
  const panelId = useId();
  const panelRef = useRef<HTMLDivElement>(null);

  // Escape closes
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("keydown", onKey); };
  }, [onClose]);

  // Focus panel on open
  useEffect(() => { panelRef.current?.focus(); }, []);

  return (
    <div
      ref={panelRef}
      className="ai-copilot-panel"
      role="dialog"
      aria-modal="true"
      aria-labelledby={`${panelId}-title`}
      tabIndex={-1}
    >
      {/* Header */}
      <div className="ai-panel-header">
        <div className="ai-panel-title" id={`${panelId}-title`}>
          <Bot size={15} aria-hidden="true" />
          AI Copilot
        </div>
        <button
          type="button"
          className="ai-panel-close"
          onClick={onClose}
          aria-label="Close AI Copilot"
        >
          <X size={16} aria-hidden="true" />
        </button>
      </div>

      {/* Tabs */}
      <div className="ai-tabs" role="tablist" aria-label="Copilot tabs">
        {(
          [
            { id: "summary" as Tab, label: "Summary", icon: <FileText size={12} /> },
            { id: "ask"     as Tab, label: "Ask",     icon: <MessageCircle size={12} /> },
            { id: "configure" as Tab, label: "Configure", icon: <Settings2 size={12} /> },
          ] as const
        ).map(({ id, label, icon }) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            className={`ai-tab${tab === id ? " active" : ""}`}
            onClick={() => { setTab(id); }}
          >
            {icon}
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "summary" && (
        <SummaryTab snapshot={snapshot} config={config} geometry={geometry} />
      )}
      {tab === "ask" && (
        <ChatTab snapshot={snapshot} config={config} geometry={geometry} />
      )}
      {tab === "configure" && (
        <ConfigureTab
          config={config}
          geometry={geometry}
          onApply={onApply}
          isRunning={isRunning}
        />
      )}
    </div>
  );
};

// ── Trigger button (rendered in MetricsSidebar header) ────────────────────

export function AICopilotTrigger({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      className="ai-copilot-trigger"
      onClick={onClick}
      aria-label="Open AI Copilot"
      title="AI Copilot analysis and configuration"
    >
      <Bot size={13} aria-hidden="true" />
      <span>AI Copilot</span>
    </button>
  );
}

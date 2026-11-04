import { CircleAlert, Info, TriangleAlert } from "lucide-react";
import "../insights/Insights.css";
import { sortMessages } from "./messages";
import type { MessageSeverity, ValidationMessage } from "./types";

const ICON = { error: CircleAlert, warning: TriangleAlert, info: Info };
const WORD: Record<MessageSeverity, string> = {
  error: "Error",
  warning: "Warning",
  info: "Note",
};

export function MessageList({ messages }: { messages: ValidationMessage[] }) {
  if (messages.length === 0) {
    return <p className="ins-muted">No messages.</p>;
  }
  return (
    <ul className="ins-messages" aria-label="Validation messages">
      {sortMessages(messages).map((m, i) => {
        const Icon = ICON[m.severity];
        const where = [
          m.line != null ? `line ${String(m.line)}` : null,
          m.element ? `element ${m.element}` : null,
        ].filter(Boolean);
        return (
          <li
            key={`${m.code}-${String(i)}`}
            className={`ins-message is-${m.severity}`}
          >
            <Icon size={16} aria-hidden="true" />
            <div>
              <strong>{WORD[m.severity]}:</strong> {m.message}
              {where.length > 0 && (
                <span className="ins-message__where">{where.join(", ")}</span>
              )}
              {m.hint && <span className="ins-message__where">{m.hint}</span>}
            </div>
          </li>
        );
      })}
    </ul>
  );
}

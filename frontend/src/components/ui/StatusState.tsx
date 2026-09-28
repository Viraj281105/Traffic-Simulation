import type { ReactNode } from "react";
import {
  CircleAlert,
  CircleCheck,
  CloudOff,
  Info,
  TriangleAlert,
} from "lucide-react";
import { UrbanFlowLogo } from "./UrbanFlowLogo";

export type StatusTone =
  "empty" | "info" | "success" | "warning" | "error" | "unavailable";

const ICONS: Record<Exclude<StatusTone, "empty">, typeof Info> = {
  info: Info,
  success: CircleCheck,
  warning: TriangleAlert,
  error: CircleAlert,
  unavailable: CloudOff,
};

/**
 * The one visual system for empty, success, warning, error and unavailable
 * states. The tone is carried by the icon *and* the words, never colour
 * alone. Loading uses UrbanFlowLoader (ui/Loader.tsx), which shares the
 * .uf-state frame.
 */
export function StatusState({
  tone,
  title,
  children,
  actions,
  compact = false,
  role,
  headingLevel,
  className = "",
}: {
  tone: StatusTone;
  title: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
  compact?: boolean;
  /** "alert" for errors that appear in response to an action. */
  role?: "status" | "alert";
  /** Render the title as a heading when the state is the page's content. */
  headingLevel?: 1 | 2 | 3;
  className?: string;
}) {
  const Title = headingLevel ? (`h${String(headingLevel)}` as "h1") : "p";
  const Icon = tone === "empty" ? null : ICONS[tone];
  return (
    <div
      className={[
        "uf-state",
        `uf-state--${tone}`,
        compact ? "uf-state--compact" : "",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      role={role}
    >
      <span className="uf-state__icon" aria-hidden="true">
        {Icon ? (
          <Icon size={compact ? 18 : 22} strokeWidth={1.8} />
        ) : (
          <UrbanFlowLogo size={compact ? 22 : 30} />
        )}
      </span>
      <Title className="uf-state__title">{title}</Title>
      {children && <div className="uf-state__body">{children}</div>}
      {actions && <div className="uf-state__actions">{actions}</div>}
    </div>
  );
}

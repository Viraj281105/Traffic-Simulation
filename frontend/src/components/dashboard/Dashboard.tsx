import type { ReactNode } from "react";
import { Info } from "lucide-react";
import "./Dashboard.css";

export type Tone = "neutral" | "good" | "warn" | "bad" | "info" | "accent";

/** Page header: eyebrow, title, lead text, and an optional action slot. */
export function PageHero({
  eyebrow = "Experiments",
  title,
  children,
  aside,
}: {
  eyebrow?: string;
  title: string;
  children: ReactNode;
  aside?: ReactNode;
}) {
  return (
    <header className="dash-hero">
      <div className="dash-hero__text">
        <p className="guided-eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p>{children}</p>
      </div>
      {aside ? <div className="dash-hero__aside">{aside}</div> : null}
    </header>
  );
}

/** A hover/focus explanation next to a label. */
export function InfoTip({ text }: { text: string }) {
  return (
    <span className="dash-tip" tabIndex={0} role="note" aria-label={text}>
      <Info size={13} aria-hidden="true" />
      <span className="dash-tip__bubble" aria-hidden="true">
        {text}
      </span>
    </span>
  );
}

/** One headline number, with an optional icon, hint and tone. Values are
 *  always supplied by the caller from real data. */
export function StatTile({
  label,
  value,
  unit,
  hint,
  icon,
  tone = "neutral",
  tip,
  children,
}: {
  label: string;
  value: ReactNode;
  unit?: string;
  hint?: ReactNode;
  icon?: ReactNode;
  tone?: Tone;
  tip?: string;
  children?: ReactNode;
}) {
  return (
    <div className={`dash-stat is-${tone}`}>
      <div className="dash-stat__head">
        <span className="dash-stat__label">
          {label}
          {tip ? <InfoTip text={tip} /> : null}
        </span>
        {icon ? (
          <span className="dash-stat__icon" aria-hidden="true">
            {icon}
          </span>
        ) : null}
      </div>
      <div className="dash-stat__value">
        {value}
        {unit ? <span className="dash-stat__unit">{unit}</span> : null}
      </div>
      {hint ? <div className="dash-stat__hint">{hint}</div> : null}
      {children}
    </div>
  );
}

export function StatGrid({ children }: { children: ReactNode }) {
  return <div className="dash-stats">{children}</div>;
}

/** A titled card. `id` labels the region for assistive technology. */
export function Panel({
  id,
  title,
  subtitle,
  actions,
  children,
  className = "",
}: {
  id: string;
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`dash-panel ${className}`} aria-labelledby={id}>
      <div className="dash-panel__head">
        <div>
          <h2 id={id}>{title}</h2>
          {subtitle ? <p className="dash-panel__sub">{subtitle}</p> : null}
        </div>
        {actions ? <div className="dash-panel__actions">{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}

export function Pill({
  tone = "neutral",
  children,
}: {
  tone?: Tone;
  children: ReactNode;
}) {
  return <span className={`dash-pill is-${tone}`}>{children}</span>;
}

/** Linear progress with a visible number; `value` is 0–1. */
export function Meter({
  value,
  label,
  tone = "accent",
}: {
  value: number;
  label: string;
  tone?: Tone;
}) {
  const pct = Math.max(0, Math.min(1, Number.isFinite(value) ? value : 0));
  return (
    <div
      className={`dash-meter is-${tone}`}
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(pct * 100)}
    >
      <span style={{ width: `${(pct * 100).toFixed(1)}%` }} />
    </div>
  );
}

/** Fixed-height frame for a chart, with a text alternative. */
export function ChartFrame({
  label,
  height = 240,
  children,
}: {
  label: string;
  height?: number;
  children: ReactNode;
}) {
  return (
    <div
      className="dash-chart"
      style={{ height }}
      role="img"
      aria-label={label}
    >
      {children}
    </div>
  );
}

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="dash-skeleton" aria-hidden="true">
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} style={{ width: `${String(92 - i * 14)}%` }} />
      ))}
    </div>
  );
}

export function EmptyHint({
  icon,
  title,
  children,
}: {
  icon?: ReactNode;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="dash-empty">
      {icon ? (
        <span className="dash-empty__icon" aria-hidden="true">
          {icon}
        </span>
      ) : null}
      <p className="dash-empty__title">{title}</p>
      {children ? <p className="dash-empty__body">{children}</p> : null}
    </div>
  );
}

/** Ordered steps with the current one marked. */
export function Stepper({
  steps,
  current,
}: {
  steps: string[];
  current: number;
}) {
  return (
    <ol className="dash-stepper" aria-label="Progress">
      {steps.map((s, i) => (
        <li
          key={s}
          className={i < current ? "is-done" : i === current ? "is-now" : ""}
          aria-current={i === current ? "step" : undefined}
        >
          <span className="dash-stepper__dot">{i + 1}</span>
          {s}
        </li>
      ))}
    </ol>
  );
}

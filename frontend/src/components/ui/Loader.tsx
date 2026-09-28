import type { ReactNode } from "react";
import { UrbanFlowLogo } from "./UrbanFlowLogo";

/**
 * UrbanFlow's loading system: the logo with its green flow travelling through
 * the junction. One mark for every loading state, shown only while real work
 * is in progress (static, gently fading, under prefers-reduced-motion).
 */

/** Just the animated mark, for an existing loading message that already
 *  carries its own text (it replaces a plain spinner in place). */
export function LoaderMark({ size = 20 }: { size?: number }) {
  return (
    <span className="uf-loader uf-loader-mark" aria-hidden="true">
      <UrbanFlowLogo size={size} animated />
    </span>
  );
}

/** A self-contained loading state: the mark over a short message, centred
 *  in its container. Announced politely to assistive technology. */
export function UrbanFlowLoader({
  label = "Loading…",
  size = 40,
  className = "",
}: {
  label?: ReactNode;
  size?: number;
  className?: string;
}) {
  return (
    <div
      className={`uf-state uf-state--loading ${className}`.trim()}
      role="status"
      aria-live="polite"
    >
      <LoaderMark size={size} />
      <p className="uf-state__title">{label}</p>
    </div>
  );
}

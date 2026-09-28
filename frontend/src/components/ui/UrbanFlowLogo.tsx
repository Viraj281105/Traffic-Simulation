import { useId } from "react";
import { LOGO_GEOMETRY, LOGO_PALETTES } from "./logoGeometry";

/**
 * The UrbanFlow mark, drawn in code (geometry in ./logoGeometry.ts). One
 * reusable component for the header, loader, empty states and dialogs.
 */

export type LogoVariant = "auto" | "light" | "dark";

export function UrbanFlowLogo({
  variant = "auto",
  size = 28,
  title,
  animated = false,
  className = "",
}: {
  variant?: LogoVariant;
  size?: number;
  /** Accessible name. Omit when the mark sits beside visible "UrbanFlow"
   *  text, so screen readers don't hear the name twice. */
  title?: string;
  /** The loader treatment: flow travels through the junction, the island
   *  breathes. Static under prefers-reduced-motion. */
  animated?: boolean;
  className?: string;
}) {
  const uid = useId().replace(/:/g, "");
  const maskId = `uf-logo-mask-${uid}`;
  const titleId = `uf-logo-title-${uid}`;
  const g = LOGO_GEOMETRY;
  const palette = variant === "auto" ? null : LOGO_PALETTES[variant];
  const road = palette?.road ?? "var(--logo-road)";
  const flow = palette?.flow ?? "var(--logo-flow)";

  const classes = ["uf-logo", animated ? "uf-logo--animated" : "", className]
    .filter(Boolean)
    .join(" ");

  return (
    <svg
      className={classes}
      width={size}
      height={size}
      viewBox={g.viewBox}
      fill="none"
      role={title ? "img" : undefined}
      aria-labelledby={title ? titleId : undefined}
      aria-hidden={title ? undefined : true}
      focusable="false"
    >
      {title && <title id={titleId}>{title}</title>}
      <defs>
        {/* Knocks the flow path (plus its separation) out of the roads. */}
        <mask
          id={maskId}
          maskUnits="userSpaceOnUse"
          x="0"
          y="0"
          width="64"
          height="64"
        >
          <rect width="64" height="64" fill="#fff" />
          <path
            d={g.flow}
            stroke="#000"
            strokeWidth={g.gapWidth}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </mask>
      </defs>
      <g mask={`url(#${maskId})`} stroke={road} strokeLinecap="round">
        {g.armRotations.map((deg) => (
          <path
            key={deg}
            d={g.arm}
            strokeWidth={g.roadWidth}
            transform={deg ? `rotate(${String(deg)} 32 32)` : undefined}
          />
        ))}
        <circle
          cx={g.ring.cx}
          cy={g.ring.cy}
          r={g.ring.r}
          strokeWidth={g.roadWidth}
        />
      </g>
      <circle
        className="uf-logo__island"
        cx={g.island.cx}
        cy={g.island.cy}
        r={g.island.r}
        fill={road}
      />
      <path
        className="uf-logo__flow"
        d={g.flow}
        stroke={flow}
        strokeWidth={g.flowWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
        pathLength={100}
      />
      {animated && (
        <path
          className="uf-logo__pulse"
          d={g.flow}
          stroke={flow}
          strokeWidth={g.flowWidth}
          strokeLinecap="round"
          strokeLinejoin="round"
          pathLength={100}
        />
      )}
    </svg>
  );
}

/** The mark with the UrbanFlow wordmark, for the app header and splash. */
export function UrbanFlowLockup({
  size = 28,
  variant = "auto",
}: {
  size?: number;
  variant?: LogoVariant;
}) {
  return (
    <span className="uf-lockup">
      <UrbanFlowLogo size={size} variant={variant} />
      <span className="uf-wordmark">
        Urban<span className="uf-wordmark__flow">Flow</span>
      </span>
    </span>
  );
}

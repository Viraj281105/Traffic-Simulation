import { useId } from "react";
import { LOGO_GEOMETRY, LOGO_PALETTES } from "./logoGeometry";

/**
 * The UrbanFlow mark, drawn in code (geometry in ./logoGeometry.ts). One
 * reusable component for the header, loader, empty states and dialogs.
 */

export type LogoVariant = "auto" | "light" | "dark";

const MASK_BOX = { x: -10, y: -10, width: 120, height: 120 } as const;

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
  /** The loader treatment: flow travels along the four paths, the central
   *  roundabout breathes. Static under prefers-reduced-motion. */
  animated?: boolean;
  className?: string;
}) {
  const uid = useId().replace(/:/g, "");
  const roadMask = `uf-logo-roads-${uid}`;
  const flowMask = `uf-logo-flow-${uid}`;
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
        {/* The flow paths (plus their separation) knocked out of the roads. */}
        <mask id={roadMask} maskUnits="userSpaceOnUse" {...MASK_BOX}>
          <rect {...MASK_BOX} fill="#fff" />
          {g.rotations.map((deg) => (
            <path
              key={deg}
              d={g.flow}
              stroke="#000"
              strokeWidth={g.gapWidth}
              transform={`rotate(${String(deg)} 50 50)`}
            />
          ))}
        </mask>
        {/* Each flow path passes under the next one anticlockwise. Applied
            inside each path's rotated frame, so one mask serves all four. */}
        <mask id={flowMask} maskUnits="userSpaceOnUse" {...MASK_BOX}>
          <rect {...MASK_BOX} fill="#fff" />
          <path
            d={g.flow}
            stroke="#000"
            strokeWidth={g.gapWidth}
            transform="rotate(-90 50 50)"
          />
        </mask>
      </defs>
      <g mask={`url(#${roadMask})`} stroke={road} strokeWidth={g.strokeWidth}>
        {g.rotations.map((deg) => (
          <path
            key={deg}
            d={g.road}
            transform={deg ? `rotate(${String(deg)} 50 50)` : undefined}
          />
        ))}
      </g>
      {g.rotations.map((deg) => (
        <g
          key={deg}
          transform={deg ? `rotate(${String(deg)} 50 50)` : undefined}
          mask={`url(#${flowMask})`}
          stroke={flow}
          strokeWidth={g.strokeWidth}
        >
          <path className="uf-logo__flow" d={g.flow} pathLength={100} />
          {animated && (
            <path className="uf-logo__pulse" d={g.flow} pathLength={100} />
          )}
        </g>
      ))}
      <circle
        className="uf-logo__ring"
        cx={g.ring.cx}
        cy={g.ring.cy}
        r={g.ring.r}
        stroke={road}
        strokeWidth={g.strokeWidth}
      />
    </svg>
  );
}

/** The mark with the UrbanFlow wordmark (URBAN bold, FLOW light), for the
 *  app header and sign-in. */
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

/**
 * One small drawing per metric explainer. They teach the idea behind the
 * measure, not a result; the card text beside each says what it counts and
 * where it stops being informative. Decorative to assistive technology.
 */
const BOX = "0 0 160 72";

function Frame({ children }: { children: React.ReactNode }) {
  return (
    <svg className="rl-svg is-tile" viewBox={BOX} aria-hidden="true">
      {children}
    </svg>
  );
}

function Cars({
  x,
  y,
  n,
  className = "rl-car",
}: {
  x: number;
  y: number;
  n: number;
  className?: string;
}) {
  return (
    <>
      {Array.from({ length: n }, (_, i) => (
        <rect
          key={i}
          className={className}
          x={x + i * 17}
          y={y}
          width="13"
          height="8"
          rx="2"
        />
      ))}
    </>
  );
}

/** Time lost against driving the same journey at the driver's own speed. */
export function DelayArt() {
  return (
    <Frame>
      <text className="rl-note" x="8" y="12">
        at own speed
      </text>
      <rect className="rl-bar" x="8" y="16" width="80" height="12" rx="2" />
      <text className="rl-note" x="8" y="44">
        actual journey
      </text>
      <rect className="rl-bar" x="8" y="48" width="80" height="12" rx="2" />
      <rect
        className="rl-bar is-accent"
        x="88"
        y="48"
        width="56"
        height="12"
        rx="2"
      />
      <text className="rl-note is-strong" x="116" y="42" textAnchor="middle">
        delay
      </text>
    </Frame>
  );
}

/** One vehicle's journey: only the near-stopped part counts as queued. */
export function QueuedArt() {
  return (
    <Frame>
      <rect className="rl-seg-go" x="8" y="22" width="44" height="14" />
      <rect className="rl-seg-warn" x="52" y="22" width="34" height="14" />
      <rect className="rl-seg-stop" x="86" y="22" width="30" height="14" />
      <rect className="rl-seg-go" x="116" y="22" width="36" height="14" />
      <text className="rl-note" x="30" y="18" textAnchor="middle">
        moving
      </text>
      <text className="rl-note" x="69" y="18" textAnchor="middle">
        rolling
      </text>
      <text className="rl-note" x="101" y="18" textAnchor="middle">
        stopped
      </text>
      <path className="rl-ink" d="M86 44 v4 h30 v-4" />
      <text className="rl-note is-strong" x="101" y="60" textAnchor="middle">
        queued time
      </text>
    </Frame>
  );
}

/** Vehicles that completed the movement through the junction. */
export function ServedArt() {
  return (
    <Frame>
      <rect className="rl-road" x="0" y="26" width="160" height="20" />
      <line className="rl-stop" x1="74" y1="26" x2="74" y2="46" />
      <Cars x={8} y={32} n={3} className="rl-car is-waiting" />
      <Cars x={84} y={32} n={4} />
      <path className="rl-ink" d="M84 22 h66" />
      <text className="rl-note is-strong" x="117" y="16" textAnchor="middle">
        served: counted
      </text>
      <text className="rl-note" x="40" y="62" textAnchor="middle">
        not yet through
      </text>
    </Frame>
  );
}

/** Vehicles waiting behind the stop line. */
export function QueueArt() {
  return (
    <Frame>
      <rect className="rl-road" x="0" y="26" width="160" height="20" />
      <line className="rl-stop" x1="122" y1="26" x2="122" y2="46" />
      <Cars x={18} y={32} n={6} />
      <path className="rl-ink" d="M18 22 v-4 h98 v4" />
      <text className="rl-note is-strong" x="67" y="12" textAnchor="middle">
        queue: vehicles waiting
      </text>
      <text className="rl-note" x="122" y="60" textAnchor="middle">
        stop line
      </text>
    </Frame>
  );
}

/** A speed trace that drops to zero twice. */
export function StopsArt() {
  return (
    <Frame>
      <line className="rl-axis" x1="10" y1="58" x2="150" y2="58" />
      <polyline
        className="rl-trace"
        points="10,24 36,24 48,56 58,56 72,24 92,24 104,56 114,56 128,24 150,24"
      />
      <circle className="rl-dot" cx="53" cy="56" r="3" />
      <circle className="rl-dot" cx="109" cy="56" r="3" />
      <text className="rl-note" x="10" y="12">
        speed
      </text>
      <text className="rl-note is-strong" x="81" y="48" textAnchor="middle">
        2 stops
      </text>
    </Frame>
  );
}

/** Median and 95th-percentile journey times: the planning time index is
 *  their ratio. */
export function ReliabilityArt() {
  return (
    <Frame>
      <path
        className="rl-bell"
        d="M10 56 C 30 56, 40 14, 62 14 C 84 14, 90 52, 112 55 C 128 56, 140 56, 150 56 Z"
      />
      <line className="rl-ink" x1="62" y1="10" x2="62" y2="58" />
      <line className="rl-ink" x1="124" y1="30" x2="124" y2="58" />
      <text className="rl-note" x="62" y="8" textAnchor="middle">
        median
      </text>
      <text className="rl-note" x="124" y="26" textAnchor="middle">
        95th
      </text>
      <text className="rl-note" x="80" y="68" textAnchor="middle">
        journey time →
      </text>
    </Frame>
  );
}

/** A gauge: the mean speed of the vehicles in the network right now. */
export function SpeedArt() {
  return (
    <Frame>
      <path className="rl-gauge" d="M40 58 A 40 40 0 0 1 120 58" />
      <line className="rl-needle" x1="80" y1="58" x2="102" y2="30" />
      <circle className="rl-dot" cx="80" cy="58" r="4" />
      <text className="rl-note" x="34" y="68" textAnchor="middle">
        0
      </text>
      <text className="rl-note is-strong" x="80" y="20" textAnchor="middle">
        right now
      </text>
    </Frame>
  );
}

/** Two vehicles on crossing paths: how close they come in time. */
export function CloseApproachArt() {
  return (
    <Frame>
      <rect className="rl-road" x="70" y="0" width="20" height="72" />
      <rect className="rl-road" x="0" y="26" width="160" height="20" />
      <rect className="rl-car" x="74" y="50" width="8" height="14" rx="2" />
      <rect className="rl-car" x="30" y="32" width="14" height="8" rx="2" />
      <circle className="rl-conflict" cx="80" cy="36" r="5" />
      <path className="rl-ink" d="M48 36 h22" />
      <path className="rl-ink" d="M78 46 v-4" />
      <text className="rl-note is-strong" x="124" y="58" textAnchor="middle">
        time to reach
      </text>
      <text className="rl-note is-strong" x="124" y="68" textAnchor="middle">
        the same point
      </text>
    </Frame>
  );
}

/** A measure UrbanFlow does not have. */
export function NotModelledArt() {
  return (
    <Frame>
      <rect className="rl-empty" x="30" y="14" width="100" height="44" rx="8" />
      <text className="rl-note is-strong" x="80" y="40" textAnchor="middle">
        not modelled
      </text>
    </Frame>
  );
}

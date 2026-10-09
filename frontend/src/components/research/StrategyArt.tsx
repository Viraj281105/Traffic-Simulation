/**
 * Purpose-built schematics of the three controls the study compares. They
 * draw only mechanics the engine implements: right-hand traffic, a
 * counter-clockwise ring, the paired north–south / east–west signal plan,
 * stop-line detection for the adaptive signal, and gap acceptance at a
 * roundabout entry. Proportions are schematic, not to scale. The figures in
 * the bottom strips are the defaults in types/config.ts.
 */
import { ADAPTIVE_DEFAULTS, DEFAULT_CONFIG_VALUES } from "../../types/config";

const { greenDuration, yellowDuration, allRedDuration } = DEFAULT_CONFIG_VALUES;
const { minGreen, maxGreen, extensionStep } = ADAPTIVE_DEFAULTS;
const CRITICAL_GAP = DEFAULT_CONFIG_VALUES.criticalGap;

const CX = 160;
const CY = 65;

/** Two crossing two-lane roads: ground, asphalt, centre lines. */
function Roads({ ring = false }: { ring?: boolean }) {
  return (
    <>
      <rect className="rl-ground" x="0" y="0" width="320" height="132" />
      <rect className="rl-road" x="138" y="0" width="44" height="132" />
      <rect className="rl-road" x="0" y="43" width="320" height="44" />
      {!ring && (
        <>
          <line className="rl-centre" x1="160" y1="0" x2="160" y2="43" />
          <line className="rl-centre" x1="160" y1="87" x2="160" y2="132" />
          <line className="rl-centre" x1="0" y1="65" x2="138" y2="65" />
          <line className="rl-centre" x1="182" y1="65" x2="320" y2="65" />
        </>
      )}
    </>
  );
}

function Car({
  x,
  y,
  across = false,
  className = "rl-car",
}: {
  x: number;
  y: number;
  across?: boolean;
  className?: string;
}) {
  return (
    <rect
      className={className}
      x={x}
      y={y}
      width={across ? 14 : 8}
      height={across ? 8 : 14}
      rx="2"
    />
  );
}

/** Signal head: a dark housing with one lit lamp. */
function Head({
  x,
  y,
  state,
}: {
  x: number;
  y: number;
  state: "green" | "red";
}) {
  return (
    <g>
      <rect
        className="rl-head"
        x={x - 5}
        y={y - 5}
        width="10"
        height="10"
        rx="3"
      />
      <circle
        className={state === "green" ? "rl-lamp-go" : "rl-lamp-stop"}
        cx={x}
        cy={y}
        r="3"
      />
    </g>
  );
}

/** Stop lines on the four approaches (right-hand traffic). */
function StopLines() {
  return (
    <>
      <line className="rl-stop" x1="138" y1="43" x2="160" y2="43" />
      <line className="rl-stop" x1="160" y1="87" x2="182" y2="87" />
      <line className="rl-stop" x1="138" y1="65" x2="138" y2="87" />
      <line className="rl-stop" x1="182" y1="43" x2="182" y2="65" />
    </>
  );
}

/** Traffic released on N–S, queued on E–W (shared by both signals). */
function PhaseTraffic() {
  return (
    <>
      <Car x={145} y={14} />
      <Car x={145} y={54} />
      <Car x={168} y={104} />
      <Car x={168} y={70} />
      <Car x={96} y={72} across />
      <Car x={114} y={72} across />
      <Car x={194} y={51} across />
      <Car x={212} y={51} across />
    </>
  );
}

function Heads() {
  return (
    <>
      <Head x={131} y={37} state="green" />
      <Head x={189} y={93} state="green" />
      <Head x={131} y={94} state="red" />
      <Head x={189} y={36} state="red" />
    </>
  );
}

export function FixedTimeArt() {
  const total = 2 * (greenDuration + yellowDuration + allRedDuration);
  const unit = 280 / total;
  const parts = [
    {
      cls: "rl-seg-go",
      len: greenDuration,
      label: `N–S green ${String(greenDuration)} s`,
    },
    { cls: "rl-seg-warn", len: yellowDuration, label: "" },
    { cls: "rl-seg-stop", len: allRedDuration, label: "" },
    {
      cls: "rl-seg-go",
      len: greenDuration,
      label: `E–W green ${String(greenDuration)} s`,
    },
    { cls: "rl-seg-warn", len: yellowDuration, label: "" },
    { cls: "rl-seg-stop", len: allRedDuration, label: "" },
  ];
  const starts = parts.map((_, i) =>
    parts.slice(0, i).reduce((sum, q) => sum + q.len * unit, 20),
  );
  return (
    <svg
      className="rl-svg"
      viewBox="0 0 320 196"
      role="img"
      aria-label={`Fixed-time signal: north–south traffic has a green while east–west traffic queues at red. The plan repeats ${String(greenDuration)} s of green, ${String(yellowDuration)} s of yellow and ${String(allRedDuration)} s of all-red for each pair of approaches, whether or not anyone is waiting.`}
    >
      <Roads />
      <StopLines />
      <PhaseTraffic />
      <Heads />
      <text className="rl-note" x="12" y="124">
        green: flowing
      </text>
      <text className="rl-note" x="308" y="124" textAnchor="end">
        red: queued
      </text>
      <g>
        {parts.map((p, i) => {
          const w = p.len * unit;
          const x = starts[i];
          return (
            <g key={i}>
              <rect className={p.cls} x={x} y="150" width={w} height="22" />
              {p.label && (
                <text
                  className="rl-seg-text"
                  x={x + w / 2}
                  y="165"
                  textAnchor="middle"
                >
                  {p.label}
                </text>
              )}
            </g>
          );
        })}
        <text className="rl-note" x="20" y="188">
          one cycle, repeated: yellow {yellowDuration} s, all-red{" "}
          {allRedDuration} s
        </text>
      </g>
    </svg>
  );
}

export function AdaptiveArt() {
  const scale = 280 / maxGreen;
  const minW = minGreen * scale;
  const exampleEnd = 32;
  const extW = (exampleEnd - minGreen) * scale;
  const maxW = maxGreen * scale;
  const ticks: number[] = [];
  for (let t = minGreen + extensionStep; t < exampleEnd; t += extensionStep) {
    ticks.push(t);
  }
  return (
    <svg
      className="rl-svg"
      viewBox="0 0 320 196"
      role="img"
      aria-label={`Adaptive signal: the same junction and phase plan, with a detection zone before each stop line. A green lasts at least ${String(minGreen)} s, each passing vehicle extends it, and it ends when vehicles stop passing and another approach is waiting, or at the ${String(maxGreen)} s maximum.`}
    >
      <Roads />
      <rect className="rl-zone" x="138" y="0" width="22" height="43" />
      <rect className="rl-zone" x="160" y="87" width="22" height="45" />
      <rect className="rl-zone" x="86" y="65" width="52" height="22" />
      <rect className="rl-zone" x="182" y="43" width="52" height="22" />
      <StopLines />
      <PhaseTraffic />
      <Heads />
      <text className="rl-note" x="12" y="124">
        shaded: detectors
      </text>
      <rect className="rl-seg-go" x="20" y="150" width={minW} height="22" />
      <rect
        className="rl-seg-go is-extension"
        x={20 + minW}
        y="150"
        width={extW}
        height="22"
      />
      {ticks.map((t) => (
        <line
          key={t}
          className="rl-tick"
          x1={20 + t * scale}
          y1="150"
          x2={20 + t * scale}
          y2="172"
        />
      ))}
      <rect
        className="rl-seg-open"
        x={20 + minW + extW}
        y="150"
        width={maxW - minW - extW}
        height="22"
      />
      <text
        className="rl-seg-text"
        x={20 + minW / 2}
        y="165"
        textAnchor="middle"
      >
        min {minGreen} s
      </text>
      <text className="rl-note" x="20" y="188">
        example: ends when vehicles stop passing
      </text>
    </svg>
  );
}

/** Arrowhead on the ring at angle `deg` (counter-clockwise from east). */
function RingArrow({ deg }: { deg: number }) {
  const r = 33;
  const rad = (deg * Math.PI) / 180;
  const x = CX + r * Math.cos(rad);
  const y = CY - r * Math.sin(rad);
  // Counter-clockwise tangent in screen coordinates (y points down).
  const heading = (Math.atan2(-Math.cos(rad), -Math.sin(rad)) * 180) / Math.PI;
  return (
    <polygon
      className="rl-ring-arrow"
      points="-5,-4 5,0 -5,4"
      transform={`translate(${String(x)} ${String(y)}) rotate(${String(heading)})`}
    />
  );
}

export function RoundaboutArt() {
  return (
    <svg
      className="rl-svg"
      viewBox="0 0 320 196"
      role="img"
      aria-label={`Roundabout: no signal. Vehicles circulate counter-clockwise; an entering vehicle gives way and joins the ring when it finds a gap in circulating traffic at least as long as its critical gap (${CRITICAL_GAP.toFixed(1)} s by default).`}
    >
      <Roads ring />
      <circle className="rl-ring" cx={CX} cy={CY} r="33" />
      <circle className="rl-island" cx={CX} cy={CY} r="22" />
      <RingArrow deg={45} />
      <RingArrow deg={135} />
      <RingArrow deg={225} />
      <RingArrow deg={315} />
      <line className="rl-yield" x1="160" y1="111" x2="182" y2="111" />
      <line className="rl-yield" x1="138" y1="19" x2="160" y2="19" />
      <line className="rl-yield" x1="116" y1="65" x2="116" y2="87" />
      <line className="rl-yield" x1="204" y1="43" x2="204" y2="65" />
      <Car x={166} y={116} />
      <Car x={145} y={4} />
      <Car x={92} y={72} across />
      <Car x={218} y={51} across />
      <rect
        className="rl-car is-ring"
        x="183"
        y="47"
        width="10"
        height="10"
        rx="3"
        transform="rotate(-40 188 52)"
      />
      <text className="rl-note" x="12" y="124">
        dashed: give way
      </text>
      <g>
        <line className="rl-axis" x1="20" y1="172" x2="300" y2="172" />
        <rect
          className="rl-block"
          x="20"
          y="152"
          width="46"
          height="18"
          rx="3"
        />
        <rect
          className="rl-block"
          x="82"
          y="152"
          width="30"
          height="18"
          rx="3"
        />
        <rect
          className="rl-gap-ok"
          x="176"
          y="148"
          width="92"
          height="26"
          rx="4"
        />
        <rect
          className="rl-block"
          x="132"
          y="152"
          width="34"
          height="18"
          rx="3"
        />
        <rect
          className="rl-block"
          x="270"
          y="152"
          width="30"
          height="18"
          rx="3"
        />
        <text className="rl-seg-text" x="222" y="165" textAnchor="middle">
          gap ≥ {CRITICAL_GAP.toFixed(1)} s
        </text>
        <text className="rl-note" x="20" y="188">
          enter only in a gap this long
        </text>
      </g>
    </svg>
  );
}

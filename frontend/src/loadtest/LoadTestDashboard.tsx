import "../netcommon/network.css";
import { StatGrid, StatTile } from "../components/dashboard/Dashboard";
import { dateTime, isNum, num, percent } from "../netcommon/format";
import type { LoadTestSummary } from "./types";

const BARS = ["avg", "med", "p90", "p95", "p99", "max"] as const;
const BAR_LABEL: Record<(typeof BARS)[number], string> = {
  avg: "Average",
  med: "Median",
  p90: "90th percentile",
  p95: "95th percentile",
  p99: "99th percentile",
  max: "Slowest",
};

function ms(v: number | null | undefined): string {
  return isNum(v) ? `${num(v, 0)} ms` : "Not available";
}

function rate(v: number | null | undefined): string {
  return isNum(v) ? percent(v, v < 0.01 ? 2 : 1) : "Not available";
}

/** Horizontal bars of the latency distribution on one scale. */
export function LatencyBars({
  latency,
}: {
  latency: LoadTestSummary["latencyMs"];
}) {
  const values = BARS.map((k) => latency[k]);
  const top = Math.max(1, ...values.filter(isNum));
  return (
    <svg
      className="nw-svg"
      viewBox="0 0 640 190"
      role="img"
      aria-label={`Response time: ${BARS.map((k) => `${BAR_LABEL[k]} ${ms(latency[k])}`).join(", ")}`}
    >
      {BARS.map((k, i) => {
        const v = latency[k];
        const y = 8 + i * 29;
        return (
          <g key={k}>
            <text className="nw-svg__label" x={0} y={y + 14}>
              {BAR_LABEL[k]}
            </text>
            {isNum(v) ? (
              <>
                <rect
                  x={120}
                  y={y}
                  width={Math.max(2, (v / top) * 420)}
                  height={20}
                  fill="var(--color-accent)"
                  opacity={k === "p95" ? 1 : 0.55}
                />
                <text
                  className="nw-svg__tick"
                  x={126 + (v / top) * 420}
                  y={y + 14}
                >
                  {num(v, 0)} ms
                </text>
              </>
            ) : (
              <text className="nw-svg__tick" x={120} y={y + 14}>
                not available
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

/** One load-test run: the headline numbers, whether each threshold held, the
 *  response-time spread and the slowest endpoints. */
export function LoadTestDashboard({
  summary: s,
}: {
  summary: LoadTestSummary;
}) {
  const failed = s.thresholds.filter((t) => !t.passed);
  const allPass = s.thresholds.length > 0 && failed.length === 0;
  return (
    <div className="nw-stack">
      <p className="nw-headline">
        <span
          className={`nw-badge ${allPass ? "is-pass" : "is-fail"}`}
          role="status"
        >
          {s.thresholds.length === 0
            ? "NO THRESHOLDS"
            : allPass
              ? "ALL THRESHOLDS PASSED"
              : `${String(failed.length)} OF ${String(s.thresholds.length)} THRESHOLDS FAILED`}
        </span>{" "}
        {s.scenario} against {s.target}
      </p>
      <p className="nw-muted">
        {s.tool}
        {s.toolVersion ? ` ${s.toolVersion}` : ""}, finished{" "}
        {dateTime(s.generatedAt)}, ran {num(s.durationSeconds, 0)} s.
      </p>
      <StatGrid>
        <StatTile
          label="95th percentile response time"
          value={
            isNum(s.latencyMs.p95) ? num(s.latencyMs.p95, 0) : "Not available"
          }
          unit={isNum(s.latencyMs.p95) ? "ms" : undefined}
          hint="95% of requests were faster than this"
          tone={
            s.thresholds.some(
              (t) => t.metric === "http_req_duration" && !t.passed,
            )
              ? "bad"
              : "neutral"
          }
        />
        <StatTile
          label="Error rate"
          value={rate(s.requests.errorRate)}
          hint={`${num(s.requests.failed, 0)} of ${num(s.requests.total, 0)} requests failed`}
          tone={
            s.thresholds.some(
              (t) => t.metric === "http_req_failed" && !t.passed,
            )
              ? "bad"
              : "neutral"
          }
        />
        <StatTile
          label="Virtual users"
          value={num(s.vus.peak, 0)}
          hint={`at most ${num(s.vus.max, 0)} allowed`}
        />
        <StatTile
          label="Requests per second"
          value={
            isNum(s.requests.ratePerSecond)
              ? num(s.requests.ratePerSecond, 1)
              : "Not available"
          }
        />
      </StatGrid>

      <h3 className="nw-headline">Thresholds</h3>
      {s.thresholds.length === 0 ? (
        <p>The test set no pass or fail thresholds.</p>
      ) : (
        <div className="uf-table-wrap nw-scroll">
          <table className="uf-table">
            <caption>
              Each rule the test script set, and whether the run met it.
            </caption>
            <thead>
              <tr>
                <th scope="col">Rule</th>
                <th scope="col">Measure</th>
                <th scope="col">Condition</th>
                <th scope="col">Result</th>
              </tr>
            </thead>
            <tbody>
              {s.thresholds.map((t) => (
                <tr key={`${t.metric}-${t.expression}`}>
                  <th scope="row">{t.name}</th>
                  <td>{t.metric}</td>
                  <td>
                    <code>{t.expression}</code>
                  </td>
                  <td>
                    <span
                      className={`nw-badge ${t.passed ? "is-pass" : "is-fail"}`}
                    >
                      {t.passed ? "Pass" : "Fail"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h3 className="nw-headline">Response time</h3>
      <LatencyBars latency={s.latencyMs} />
      <p className="nw-muted">
        Checks passed: {num(s.checks.passes, 0)}; failed:{" "}
        {num(s.checks.fails, 0)}. Fastest request {ms(s.latencyMs.min)}.
      </p>

      {s.endpoints && s.endpoints.length > 0 && (
        <>
          <h3 className="nw-headline">By endpoint</h3>
          <div className="uf-table-wrap nw-scroll">
            <table className="uf-table">
              <caption>
                Requests, 95th percentile response time and error rate per
                endpoint.
              </caption>
              <thead>
                <tr>
                  <th scope="col">Endpoint</th>
                  <th scope="col">Requests</th>
                  <th scope="col">95th percentile</th>
                  <th scope="col">Error rate</th>
                </tr>
              </thead>
              <tbody>
                {s.endpoints.map((e) => (
                  <tr key={e.name}>
                    <th scope="row">{e.name}</th>
                    <td className="nw-num">{num(e.requests, 0)}</td>
                    <td className="nw-num">{ms(e.p95Ms)}</td>
                    <td className="nw-num">{rate(e.errorRate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

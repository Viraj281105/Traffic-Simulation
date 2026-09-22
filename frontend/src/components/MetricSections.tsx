import React from "react";
import {
  METRIC_GROUPS,
  METRICS_BY_GROUP,
  formatDifference,
  formatMetric,
  metricDifference,
  metricLabel,
  metricState,
  type MetricContext,
  type MetricGroupId,
  WARMUP_NOTE,
} from "../metrics/catalog";
import "./MetricSections.css";

const DEFAULT_COLLAPSED: MetricGroupId[] = ["diagnostic"];

/** Per-cell qualifier; warm-up is announced once by the panel instead. */
function CellNote({ note }: { note: string | undefined }) {
  if (!note || note === WARMUP_NOTE) return null;
  return <span className="metric-note">{note}</span>;
}

function GroupFrame({
  id,
  title,
  blurb,
  collapsed,
  children,
}: {
  id: MetricGroupId;
  title: string;
  blurb: string;
  collapsed: boolean;
  children: React.ReactNode;
}) {
  return (
    <details className="metric-group" open={!collapsed} data-group={id}>
      <summary>
        <h3 className="metric-group-title">{title}</h3>
      </summary>
      <p className="metric-group-blurb">{blurb}</p>
      {children}
    </details>
  );
}

/** Every backend metric for one run, grouped. */
export function MetricSections({
  ctx,
  collapsed = DEFAULT_COLLAPSED,
}: {
  ctx: MetricContext;
  collapsed?: MetricGroupId[];
}) {
  return (
    <div className="metric-sections">
      {METRIC_GROUPS.map((group) => (
        <GroupFrame
          key={group.id}
          id={group.id}
          title={group.title}
          blurb={group.blurb}
          collapsed={collapsed.includes(group.id)}
        >
          <dl className="metric-dl">
            {METRICS_BY_GROUP[group.id].map((def) => {
              const state = metricState(def, ctx);
              return (
                <div
                  className="metric-dl-row"
                  key={def.key}
                  title={def.description}
                  data-metric={def.key}
                >
                  <dt>{metricLabel(def, ctx.metrics ?? undefined)}</dt>
                  <dd
                    className={state.kind === "none" ? "is-empty" : undefined}
                  >
                    {formatMetric(def, ctx)}
                    {state.note && (
                      <span className="metric-note">{state.note}</span>
                    )}
                  </dd>
                </div>
              );
            })}
          </dl>
        </GroupFrame>
      ))}
    </div>
  );
}

/** Every backend metric for a signal/roundabout pair, side by side. The last
 *  column is the plain difference (roundabout − signal) in the metric's own
 *  units; nothing is ranked or coloured as better or worse. */
export function ComparisonSections({
  signal,
  roundabout,
  collapsed = DEFAULT_COLLAPSED,
  compact = false,
}: {
  signal: MetricContext;
  roundabout: MetricContext;
  collapsed?: MetricGroupId[];
  compact?: boolean;
}) {
  const labelSource = signal.metrics ?? roundabout.metrics ?? undefined;
  return (
    <div className={`metric-sections${compact ? " compact" : ""}`}>
      {METRIC_GROUPS.map((group) => (
        <GroupFrame
          key={group.id}
          id={group.id}
          title={group.title}
          blurb={group.blurb}
          collapsed={collapsed.includes(group.id)}
        >
          <table className="comparison-grid">
            <thead>
              <tr>
                <th scope="col">Metric</th>
                <th scope="col">Signal</th>
                <th scope="col">Roundabout</th>
                <th scope="col" title="Roundabout minus signal">
                  Δ (R−S)
                </th>
              </tr>
            </thead>
            <tbody>
              {METRICS_BY_GROUP[group.id].map((def) => {
                const s = metricState(def, signal);
                const r = metricState(def, roundabout);
                return (
                  <tr
                    key={def.key}
                    title={def.description}
                    data-metric={def.key}
                  >
                    <th scope="row">
                      {metricLabel(def, labelSource)}
                      {compact && def.unit && (
                        <span className="unit-suffix"> ({def.unit})</span>
                      )}
                    </th>
                    <td className={s.kind === "none" ? "is-empty" : undefined}>
                      {formatMetric(def, signal, !compact)}
                      <CellNote note={s.note} />
                    </td>
                    <td className={r.kind === "none" ? "is-empty" : undefined}>
                      {formatMetric(def, roundabout, !compact)}
                      <CellNote note={r.note} />
                    </td>
                    <td className="diff">
                      {formatDifference(
                        def,
                        metricDifference(def, signal, roundabout),
                        !compact,
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </GroupFrame>
      ))}
    </div>
  );
}

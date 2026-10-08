import type { RunningMetrics, VehicleClass } from "../../types/simulation";
import { VEHICLE_CLASSES } from "../../vehicles/vehicleClasses";
import { seconds } from "../../metrics/plainLanguage";

type Breakdown = RunningMetrics["vehicleTypeBreakdown"];

/**
 * Per-vehicle-class results (V1.1): how many of each kind got through and the
 * time each lost, at both junctions. Shown only for mixed traffic: with
 * cars only it would repeat the headline figure.
 *
 * The figures are the backend's own per-class split of the delay the
 * headline uses (metrics.vehicleTypeBreakdown), so they reconcile with it.
 */
export function VehicleClassResults({
  signal,
  roundabout,
}: {
  signal: Breakdown;
  roundabout: Breakdown;
}) {
  const classes = VEHICLE_CLASSES.filter(
    (c) =>
      (signal?.[c.id]?.exited ?? 0) + (roundabout?.[c.id]?.exited ?? 0) > 0,
  );
  if (classes.length < 2) return null;
  const cell = (b: Breakdown, id: VehicleClass) => {
    const entry = b?.[id];
    if (!entry || entry.exited === 0) return <td colSpan={2}>none through</td>;
    return (
      <>
        <td>{String(entry.exited)}</td>
        <td>{seconds(entry.averageDelay)}</td>
      </>
    );
  };
  return (
    <section className="results-section" aria-labelledby="r-classes">
      <h2 id="r-classes">Which vehicles lose the time?</h2>
      <p>
        Each kind of vehicle drives differently, so the junctions treat them
        differently: a bus or truck takes longer to get going and needs a bigger
        gap, a motorcycle slips through sooner.
      </p>
      <div className="table-scroll">
        <table className="plain-table">
          <thead>
            <tr>
              <th scope="col" rowSpan={2}>
                Vehicle
              </th>
              <th scope="colgroup" colSpan={2}>
                Traffic signal
              </th>
              <th scope="colgroup" colSpan={2}>
                Roundabout
              </th>
            </tr>
            <tr>
              <th scope="col">Got through</th>
              <th scope="col">Time lost (avg)</th>
              <th scope="col">Got through</th>
              <th scope="col">Time lost (avg)</th>
            </tr>
          </thead>
          <tbody>
            {classes.map((c) => (
              <tr key={c.id}>
                <th scope="row">
                  <span
                    className="class-swatch"
                    style={{ background: c.color }}
                    aria-hidden="true"
                  />{" "}
                  {c.label}
                </th>
                {cell(signal, c.id)}
                {cell(roundabout, c.id)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="results-note">
        Few buses or trucks get through in a short run, so their averages move a
        lot from one traffic pattern to the next.
      </p>
    </section>
  );
}

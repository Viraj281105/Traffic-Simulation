import { Download } from "lucide-react";
import { lowerDelayOf, type ValidationResult } from "./validationModel";

/** Every seed's paired values, with which control had the lower delay. */
export function SeedRunsTable({
  result,
  onExportCsv,
}: {
  result: ValidationResult;
  onExportCsv: () => void;
}) {
  const exportValidationCSV = onExportCsv;
  return (
    <div className="seed-runs-table-wrapper">
      <div className="runs-table-header">
        <div className="table-header-titles">
          <h4>Synchronized Raw Trials Dataset ({result.numSeeds} Seeds)</h4>
          <span className="table-meta-hint">
            Paired trials executed with identical Poisson vehicle spawn seeds
          </span>
        </div>
        <button
          type="button"
          className="table-export-btn"
          onClick={exportValidationCSV}
        >
          <Download size={14} aria-hidden="true" className="uf-glyph" />{" "}
          Download CSV
        </button>
      </div>

      <div className="validation-table-scroll-container">
        <table>
          <thead>
            <tr>
              <th>Seed #</th>
              <th>Signal Delay</th>
              <th>Rnd Delay</th>
              <th>Δ Delay (s)</th>
              <th>Signal Tput</th>
              <th>Rnd Tput</th>
              <th>Signal Queue</th>
              <th>Rnd Queue</th>
              <th title="Lower mean delay for this seed">Lower delay</th>
            </tr>
          </thead>
          <tbody>
            {result.seedRuns.map((run) => {
              const deltaDelay = run.roundabout.delay - run.signal.delay;
              const winner = lowerDelayOf(run);

              return (
                <tr key={run.seed}>
                  <td>
                    <strong className="seed-id-cell">#{run.seed}</strong>
                  </td>
                  <td>{run.signal.delay.toFixed(2)}s</td>
                  <td>{run.roundabout.delay.toFixed(2)}s</td>
                  <td
                    style={{
                      fontWeight: 700,
                    }}
                  >
                    {deltaDelay < 0 ? "" : "+"}
                    {deltaDelay.toFixed(2)}s
                  </td>
                  <td>{run.signal.throughput.toFixed(1)}</td>
                  <td>{run.roundabout.throughput.toFixed(1)}</td>
                  <td>{run.signal.queue.toFixed(2)}</td>
                  <td>{run.roundabout.queue.toFixed(2)}</td>
                  <td>
                    <span
                      className={
                        winner === "roundabout"
                          ? "seed-winner-rnd"
                          : "seed-winner-sig"
                      }
                    >
                      {winner === "roundabout"
                        ? "Roundabout"
                        : winner === "signal"
                          ? "Signal"
                          : "About the same"}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

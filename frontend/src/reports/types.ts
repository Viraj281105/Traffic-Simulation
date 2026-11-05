/** Contract: GET /api/v3/experiments/{experimentId}/report.
 *  See src/CONTRACTS.md. The server assembles the report from computed
 *  results only; the screen lays it out for the browser's print-to-PDF. */
import type { ComparisonResult } from "../comparison/types";
import type { RunMetrics } from "../kpis/types";
import type { SensitivityResult } from "../sensitivity/types";

export interface ReportDocument {
  experimentId: string;
  title: string;
  generatedAt: string;
  /** Shown first, before any result (decision-report rule). */
  assumptions: string[];
  limitations: string[];
  summary: {
    text: string;
    /** True when the server's check found every number in the text in the
     *  computed results. */
    grounded: boolean;
  };
  comparison: ComparisonResult | null;
  sensitivity: SensitivityResult | null;
  metrics: RunMetrics | null;
  /** Reproducibility record: re-running from this gives the same result. */
  manifest: {
    seed: number | null;
    configHash: string | null;
    codeVersion: string | null;
    inputVersion: string | null;
  };
}

/** Contract: GET /api/v3/experiments/{experimentId}/sensitivity?metric=
 *  See src/CONTRACTS.md. */

export interface SensitivityInput {
  id: string;
  label: string;
  unit?: string | null;
  /** Share of the outcome's variation this input explains alone (0 to 1):
   *  the first-order index. */
  firstOrder: number;
  /** Including its interactions with other inputs (0 to 1), if computed. */
  total?: number | null;
  /** Interval for `firstOrder`, if the method gives one. */
  ci?: [number, number] | null;
}

export interface SensitivityResult {
  experimentId: string;
  metric: { id: string; label: string; unit: string };
  method: {
    /** e.g. "Sobol indices". */
    name: string;
    /** Seed that makes the ranking reproducible. */
    seed: number;
    samples: number;
    note?: string | null;
  };
  /** In any order; the screen sorts by `total`, then `firstOrder`. */
  inputs: SensitivityInput[];
}

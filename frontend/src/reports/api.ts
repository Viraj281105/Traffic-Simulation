import { V3, getJson } from "../insights/http";
import type { ReportDocument } from "./types";

export function getReport(experimentId: string): Promise<ReportDocument> {
  return getJson(
    `${V3}/experiments/${encodeURIComponent(experimentId)}/report`,
  );
}

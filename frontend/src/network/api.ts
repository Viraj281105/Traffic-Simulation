import { API_BASE_URL } from "../config";
import { getAuthToken } from "../auth/cognito";
import { InsightsApiError, V3, postJson } from "../insights/http";
import type {
  ImportPreview,
  ImportPreviewRequest,
  NetworkFormat,
  ValidationResult,
} from "./types";

/** Largest file the screen sends; the server enforces its own limit too. */
export const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;

/** Upload a network file for validation. The server answers 200 with the
 *  messages even when the file is unusable; a refused request (too large,
 *  wrong type) is an InsightsApiError carrying the server's reason. */
export async function validateNetworkFile(
  file: File,
  format: NetworkFormat = "auto",
  signal?: AbortSignal,
): Promise<ValidationResult> {
  const body = new FormData();
  body.append("file", file, file.name);
  body.append("format", format);
  const token = await getAuthToken();
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${V3}/networks/validate`, {
      method: "POST",
      headers,
      body,
      signal,
    });
  } catch {
    throw new InsightsApiError(0, ["The server could not be reached."]);
  }
  if (!response.ok) {
    const problem = (await response.json().catch(() => null)) as {
      error?: { message?: string };
    } | null;
    throw new InsightsApiError(response.status, [
      problem?.error?.message ?? (response.statusText || "Upload failed"),
    ]);
  }
  return (await response.json()) as ValidationResult;
}

export function previewRoadImport(
  request: ImportPreviewRequest,
): Promise<ImportPreview> {
  return postJson(`${V3}/networks/import/preview`, request);
}

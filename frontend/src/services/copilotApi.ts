/**
 * Typed fetch wrappers for the /api/ai/* endpoints.
 *
 * The Groq API key lives exclusively in the backend environment; this module
 * only talks to our own FastAPI server.
 */

import { API_BASE_URL } from "../config";
import { getAuthToken } from "../auth/cognito";

const BASE = API_BASE_URL;

// ── Types ─────────────────────────────────────────────────────────────────

export interface ConversationTurn {
  role: "user" | "assistant";
  content: string;
}

export type CopilotGeometry = "fixed_time_signal" | "roundabout" | "comparison";

export interface SummaryRequest {
  metrics: Record<string, unknown>;
  config: Record<string, unknown>;
  geometry: CopilotGeometry;
  elapsed_seconds?: number | null;
}

export interface SummaryResponse {
  summary: string;
  bullets: string[];
  warnings: string[];
  fallback: boolean;
}

export interface ChatRequest {
  question: string;
  metrics: Record<string, unknown>;
  config: Record<string, unknown>;
  geometry: CopilotGeometry;
  history: ConversationTurn[];
}

export interface ChatResponse {
  answer: string;
  fallback: boolean;
}

export interface PatchRequest {
  instruction: string;
  current_config: Record<string, unknown>;
  geometry: "fixed_time_signal" | "roundabout";
}

export interface ConfigPatch {
  patch: Record<string, unknown>;
  merged: Record<string, unknown>;
  assumptions: string[];
  warnings: string[];
  clarification: string | null;
  fallback: boolean;
}

// ── Internal helper ───────────────────────────────────────────────────────

async function aiPost<Res>(path: string, body: unknown): Promise<Res> {
  const token = await getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const resp = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(35_000), // 35 s — backend has 30 s Groq timeout
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => resp.statusText);
    throw new Error(`AI API ${String(resp.status)}: ${text}`);
  }
  return resp.json() as Promise<Res>;
}

// ── Public API ────────────────────────────────────────────────────────────

export async function fetchSummary(req: SummaryRequest): Promise<SummaryResponse> {
  return aiPost<SummaryResponse>("/api/ai/summary", req);
}

export async function fetchChat(req: ChatRequest): Promise<ChatResponse> {
  return aiPost<ChatResponse>("/api/ai/chat", req);
}

export async function fetchPatch(req: PatchRequest): Promise<ConfigPatch> {
  return aiPost<ConfigPatch>("/api/ai/patch", req);
}

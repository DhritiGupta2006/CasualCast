/**
 * lib/api.ts — CausalCast live backend client.
 *
 * Every function here just shapes an HTTP call to backend/api and shapes
 * the JSON response back into the types the UI already uses. No math
 * happens in this file — forecasts, budget scenarios, and incrementality
 * figures are all computed by core/ on the server and returned as-is.
 * (See design doc ground rule #8: the frontend never computes forecasts
 * itself — only backend/api (live) or src/predict.py (batch) produce
 * numbers.)
 *
 * Base URL is configurable via VITE_API_BASE_URL (falls back to
 * localhost:8000, matching `uvicorn backend.api.main:app --port 8000`).
 */

import type { ForecastData, ForecastOutput } from "./forecast";

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/+$/, "") || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: init?.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : undefined,
      ...init,
    });
  } catch {
    throw new ApiError(0, "Could not reach the CausalCast backend. Is it running (uvicorn backend.api.main:app)?");
  }
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = res.statusText;
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

/** Row shape the backend's DataRow schema expects — same fields as the
 *  frontend's own ForecastData, just handed straight through. */
export type ApiDataRow = {
  date: string;
  spend: number;
  revenue: number;
  sessions?: number | null;
  channel?: string | null;
};

function toApiRows(rows: ForecastData[]): ApiDataRow[] {
  return rows.map((r) => ({
    date: r.date,
    spend: r.spend,
    revenue: r.revenue,
    sessions: r.sessions ?? undefined,
  }));
}

// ---------------------------------------------------------------------
// POST /api/upload
// ---------------------------------------------------------------------

export interface UploadResponse {
  rows: ApiDataRow[];
  row_count: number;
  notes: string[];
  anomaly_count: number;
  channel_groups: string[];
  date_range: [string, string];
}

export async function uploadCSV(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  return request<UploadResponse>("/api/upload", { method: "POST", body: form });
}

// ---------------------------------------------------------------------
// POST /api/forecast
// ---------------------------------------------------------------------

export interface ForecastApiResponse {
  results: { date: string; p10: number; p50: number; p90: number }[];
  historical: Record<string, any>[];
  stats: {
    avg_p10: number;
    avg_p50: number;
    avg_p90: number;
    confidence_range_pct: number;
    trend_direction: "up" | "down" | "flat";
    slope: number;
  };
  horizon: number;
  iterations: number;
  seed: number;
  anomaly_count: number;
  channel_groups: string[];
  weekday_factors: Record<string, number> | number[];
  notes: string[];
  warnings: string[];
}

export async function runForecast(
  rows: ForecastData[],
  opts?: { horizon?: number; iterations?: number; seed?: number }
): Promise<ForecastApiResponse> {
  return request<ForecastApiResponse>("/api/forecast", {
    method: "POST",
    body: JSON.stringify({
      rows: toApiRows(rows),
      horizon: opts?.horizon ?? 30,
      iterations: opts?.iterations ?? 1000,
      seed: opts?.seed ?? 42,
    }),
  });
}

/** Adapts the API's snake_case forecast payload into the ForecastOutput
 *  shape the existing chart/report UI was already built around. */
export function adaptForecastResponse(res: ForecastApiResponse): ForecastOutput {
  return {
    results: res.results,
    historical: res.historical.map((r) => ({
      date: r.date,
      spend: Number(r.spend ?? 0),
      revenue: Number(r.revenue ?? 0),
      sessions: Number(r.sessions ?? 0),
    })),
    stats: {
      avgP10: res.stats.avg_p10,
      avgP50: res.stats.avg_p50,
      avgP90: res.stats.avg_p90,
      confidenceRange: res.stats.confidence_range_pct,
      trendDirection: res.stats.trend_direction,
      slope: res.stats.slope,
    },
  };
}

// ---------------------------------------------------------------------
// POST /api/simulate-budget
// ---------------------------------------------------------------------

export interface BudgetScenarioApi {
  daily_spend: number;
  predicted_daily_revenue: number;
  predicted_roas: number;
  delta_spend_pct: number;
  delta_revenue_pct: number;
}

export interface SimulateBudgetResponse {
  baseline_spend: number;
  baseline_predicted_revenue: number;
  curve: { a: number; b: number; r_squared: number; n_points: number; spend_min: number; spend_max: number };
  scenarios: BudgetScenarioApi[];
}

export async function simulateBudget(
  rows: ForecastData[],
  opts?: { baselineSpend?: number; multipliers?: number[] }
): Promise<SimulateBudgetResponse> {
  return request<SimulateBudgetResponse>("/api/simulate-budget", {
    method: "POST",
    body: JSON.stringify({
      rows: toApiRows(rows),
      baseline_spend: opts?.baselineSpend ?? null,
      multipliers: opts?.multipliers ?? null,
    }),
  });
}

// ---------------------------------------------------------------------
// POST /api/insights
// ---------------------------------------------------------------------

export interface IncrementalityApi {
  baseline_revenue: number;
  avg_actual_revenue: number;
  incremental_revenue: number;
  incrementality_fraction: number;
  confidence: "high" | "medium" | "low";
  baseline_extrapolated: boolean;
  disclaimer: string;
  curve: { a: number; b: number; r_squared: number; n_points: number; spend_min: number; spend_max: number } | null;
}

export interface InsightsResponse {
  trend: {
    direction: "up" | "down" | "flat";
    slope: number;
    avg_p50: number;
    confidence_range_pct: number;
  };
  incrementality: IncrementalityApi | null;
  incrementality_disclaimer: string;
  anomaly_count: number;
  channel_groups: string[];
  top_budget_scenario: { daily_spend: number; predicted_daily_revenue: number; predicted_roas: number } | null;
  warnings: string[];
  template_summary: string;
  narration_source: "template" | "llm";
}

export async function getInsights(rows: ForecastData[]): Promise<InsightsResponse> {
  return request<InsightsResponse>("/api/insights", {
    method: "POST",
    body: JSON.stringify({ rows: toApiRows(rows) }),
  });
}

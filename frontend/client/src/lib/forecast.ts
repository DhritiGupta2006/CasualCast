export interface ForecastData {
  date: string;
  spend: number;
  revenue: number;
  sessions: number;
}

export interface ForecastResult {
  date: string;
  p10: number;
  p50: number;
  p90: number;
}

export interface ForecastStats {
  avgP10: number;
  avgP50: number;
  avgP90: number;
  confidenceRange: number;
  trendDirection: "up" | "down" | "flat";
  slope: number;
}

export interface ForecastOutput {
  results: ForecastResult[];
  historical: ForecastData[];
  stats: ForecastStats;
}

export const EXPECTED_FIELDS = ["date", "spend", "revenue", "sessions"] as const;
export const ITERATIONS = 1000;
export const HORIZON_DAYS = 30;
export const MIN_HISTORY_DAYS = 7;

/** Deterministic PRNG so a given dataset always produces the same forecast. */
function seededRandom(seed: number) {
  let s = seed % 2147483647;
  if (s <= 0) s += 2147483646;
  return function () {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

function boxMuller(rand: () => number) {
  let u = 0,
    v = 0;
  while (u === 0) u = rand();
  while (v === 0) v = rand();
  return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
}

function linearRegression(ys: number[]) {
  const n = ys.length;
  const xMean = (n - 1) / 2;
  const yMean = ys.reduce((a, b) => a + b, 0) / n;
  let num = 0,
    den = 0;
  for (let i = 0; i < n; i++) {
    num += (i - xMean) * (ys[i] - yMean);
    den += (i - xMean) ** 2;
  }
  const slope = den === 0 ? 0 : num / den;
  const intercept = yMean - slope * xMean;
  const residuals = ys.map((y, i) => y - (slope * i + intercept));
  const variance = residuals.reduce((a, r) => a + r * r, 0) / Math.max(1, n - 2);
  return { slope, intercept, stdDev: Math.sqrt(variance) };
}

function weekdaySeasonality(data: ForecastData[]) {
  const buckets: number[][] = Array.from({ length: 7 }, () => []);
  data.forEach((d) => {
    const dow = new Date(d.date).getDay();
    if (!isNaN(dow)) buckets[dow].push(d.revenue);
  });
  const overallMean = data.reduce((a, d) => a + d.revenue, 0) / data.length;
  return buckets.map((b) => {
    if (b.length === 0) return 0;
    const mean = b.reduce((a, v) => a + v, 0) / b.length;
    return mean - overallMean;
  });
}

/**
 * Monte Carlo revenue forecast: fits a linear trend + weekday-seasonality
 * model to historical revenue, then simulates ITERATIONS random 30-day
 * paths (trend + seasonal + noise drawn from historical residual volatility)
 * to produce P10/P50/P90 confidence bands per day.
 */
export function runMonteCarloForecast(data: ForecastData[]): ForecastOutput {
  const sorted = [...data].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
  const revenues = sorted.map((d) => d.revenue);
  const { slope, intercept, stdDev } = linearRegression(revenues);
  const seasonality = sorted.length >= 14 ? weekdaySeasonality(sorted) : sorted.map(() => 0);
  const lastDate = new Date(sorted[sorted.length - 1].date);
  const n = sorted.length;

  const paths: number[][] = [];
  const rand = seededRandom(42);
  for (let iter = 0; iter < ITERATIONS; iter++) {
    const path: number[] = [];
    for (let h = 1; h <= HORIZON_DAYS; h++) {
      const idx = n - 1 + h;
      const futureDate = new Date(lastDate);
      futureDate.setDate(futureDate.getDate() + h);
      const seasonal = seasonality[futureDate.getDay()] || 0;
      const noise = boxMuller(rand) * stdDev;
      path.push(Math.max(0, slope * idx + intercept + seasonal + noise));
    }
    paths.push(path);
  }

  const results: ForecastResult[] = [];
  for (let h = 0; h < HORIZON_DAYS; h++) {
    const dayValues = paths.map((p) => p[h]).sort((a, b) => a - b);
    const futureDate = new Date(lastDate);
    futureDate.setDate(futureDate.getDate() + h + 1);
    results.push({
      date: futureDate.toISOString().slice(0, 10),
      p10: Math.round(dayValues[Math.floor(ITERATIONS * 0.1)]),
      p50: Math.round(dayValues[Math.floor(ITERATIONS * 0.5)]),
      p90: Math.round(dayValues[Math.floor(ITERATIONS * 0.9)]),
    });
  }

  const avgP50 = Math.round(results.reduce((a, r) => a + r.p50, 0) / results.length);
  const avgP10 = Math.round(results.reduce((a, r) => a + r.p10, 0) / results.length);
  const avgP90 = Math.round(results.reduce((a, r) => a + r.p90, 0) / results.length);
  const confidenceRange = avgP50 > 0 ? Math.round(((avgP90 - avgP10) / avgP50) * 100) : 0;
  const trendDirection: ForecastStats["trendDirection"] = slope > 0.5 ? "up" : slope < -0.5 ? "down" : "flat";

  return {
    results,
    historical: sorted,
    stats: { avgP10, avgP50, avgP90, confidenceRange, trendDirection, slope },
  };
}

export function generateSampleData(): ForecastData[] {
  const days = 21;
  const out: ForecastData[] = [];
  const start = new Date();
  start.setDate(start.getDate() - days);
  const rand = seededRandom(7);
  let base = 4200;
  for (let i = 0; i < days; i++) {
    const d = new Date(start);
    d.setDate(d.getDate() + i);
    base += 35 + boxMuller(rand) * 40;
    const dow = d.getDay();
    const weekendLift = dow === 0 || dow === 6 ? 0.92 : 1;
    const spend = Math.round(900 + boxMuller(rand) * 60);
    const revenue = Math.max(0, Math.round(base * weekendLift + boxMuller(rand) * 180));
    const sessions = Math.round(revenue / (2.1 + boxMuller(rand) * 0.15));
    out.push({ date: d.toISOString().slice(0, 10), spend, revenue, sessions });
  }
  return out;
}

/**
 * Header synonym dictionary. Keys are normalized (lowercase, punctuation and
 * whitespace stripped) so "Time Period", "time_period" and "TimePeriod" all
 * match the same entry.
 */
const FIELD_SYNONYMS: Record<(typeof EXPECTED_FIELDS)[number], string[]> = {
  date: [
    "date", "day", "timeperiod", "period", "week", "month", "reportingdate",
    "reportdate", "timestamp", "datetime", "weekof", "weekstarting",
    "monthof", "dateperiod", "activitydate", "statdate",
  ],
  spend: [
    "spend", "cost", "adspend", "amountspent", "totalspend", "mediaspend",
    "adcost", "expense", "spendusd", "costusd", "totalcost",
  ],
  revenue: [
    "revenue", "sales", "income", "conversionvalue", "conversionsvalue",
    "totalrevenue", "revenueusd", "grossrevenue", "totalsales", "orderrevenue",
    "conversionvalueall", "totalconversionvalue",
  ],
  sessions: [
    "sessions", "visits", "traffic", "clicks", "users", "pageviews",
    "impressions", "conversions", "visitors", "videoviews", "engagements",
  ],
};

/** Columns that identify an entity/dimension rather than a metric — never
 *  auto-mapped, but useful to report back as "ignored" so the user can see
 *  what was set aside (e.g. CampaignId, CampaignName, CampaignType). */
const ID_LIKE_PATTERN = /(^id$|id$|^uuid$|^key$|name$|type$|category$|^index$|^unnamed)/;

/** Per-unit rate metrics (cost-per-click, click-through-rate, etc.) and
 *  planned/target figures (budget) are never valid totals for spend,
 *  revenue, or sessions — exclude them from candidacy outright so they
 *  can't be picked even via a content-based fallback. */
const NON_METRIC_PATTERN = /(^cpc$|^cpm$|^cpa$|^cpl$|^ctr$|^cvr$|^roas$|^rpm$|^aov$|perclick|permille|perimpression|perconversion|peracquisition|perlead|budget)/;

function normalizeHeader(h: string): string {
  return h.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function isDateLike(value: string): boolean {
  const s = (value ?? "").trim();
  if (!s) return false;
  if (/^-?\d+(\.\d+)?$/.test(s)) return false; // plain number — not a date
  const patterns = [
    /^\d{4}-\d{1,2}-\d{1,2}([ T]\d{1,2}:\d{2}(:\d{2})?)?$/,
    /^\d{1,2}\/\d{1,2}\/\d{2,4}$/,
    /^\d{1,2}-\d{1,2}-\d{2,4}$/,
    /^\d{4}\/\d{1,2}\/\d{1,2}$/,
    /^[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4}$/,
  ];
  if (patterns.some((p) => p.test(s))) return true;
  return !isNaN(Date.parse(s));
}

function isNumericLike(value: string): boolean {
  const s = (value ?? "").trim();
  if (!s) return false;
  return !isNaN(parseFloat(s)) && isFinite(Number(s.replace(/[$,%]/g, "")));
}

/** Fraction of sampled rows for which `test` returns true (0–1). */
function sampleScore(rows: Record<string, any>[], header: string, test: (v: string) => boolean): number {
  const sample = rows.slice(0, 25);
  if (!sample.length) return 0;
  const hits = sample.filter((r) => test(String(r[header] ?? ""))).length;
  return hits / sample.length;
}

/**
 * Auto-detects which raw column corresponds to each expected field, using
 * header-name matching first and falling back to content sniffing (does the
 * column actually contain dates / numbers?) when headers are unfamiliar —
 * e.g. Bing/Google Ads exports using "TimePeriod" instead of "date", or
 * "Clicks" as a stand-in for "sessions". This lets most real-world exports
 * work with no manual mapping step at all.
 */
export function guessMapping(headers: string[], rows: Record<string, any>[] = []): Record<string, string> {
  const mapping: Record<string, string> = {};
  const used = new Set<string>();
  const normalized = headers.map((h) => ({ raw: h, norm: normalizeHeader(h) }));

  // Process the more distinctive fields first to avoid collisions.
  const order: (typeof EXPECTED_FIELDS)[number][] = ["date", "revenue", "spend", "sessions"];

  order.forEach((field) => {
    const synonyms = FIELD_SYNONYMS[field];
    let best = { header: "", score: 0 };

    normalized.forEach(({ raw, norm }) => {
      if (used.has(raw) || !norm) return;
      if (field !== "date" && (ID_LIKE_PATTERN.test(norm) || NON_METRIC_PATTERN.test(norm)) && !synonyms.includes(norm)) return;

      let score = 0;
      if (synonyms.includes(norm)) {
        score = 100;
      } else if (synonyms.some((s) => norm.includes(s) || s.includes(norm))) {
        score = 70;
      }

      // Content-based fallback for headers that don't match by name at all.
      if (score === 0 && rows.length) {
        if (field === "date") {
          const frac = sampleScore(rows, raw, isDateLike);
          if (frac >= 0.7) score = 50 + frac * 20;
        } else {
          const frac = sampleScore(rows, raw, isNumericLike);
          // Weaker signal — only worth using if nothing name-based turns up,
          // and never for a column that already looks like a date.
          if (frac >= 0.8 && !sampleScore(rows, raw, isDateLike)) score = 25 + frac * 10;
        }
      }

      if (score > best.score) best = { header: raw, score };
    });

    if (best.header) {
      mapping[field] = best.header;
      used.add(best.header);
    } else {
      mapping[field] = "";
    }
  });

  return mapping;
}

/** Headers that weren't used in the mapping — shown to the user as an FYI
 *  so it's clear extra columns (campaign id, type, budget, etc.) were seen
 *  and intentionally set aside, not lost. */
export function unmappedHeaders(headers: string[], mapping: Record<string, string>): string[] {
  const used = new Set(Object.values(mapping).filter(Boolean));
  return headers.filter((h) => !used.has(h));
}

/** Some ad platforms (notably Google Ads' reporting API) export currency
 *  fields in "micros" — millionths of the currency unit — e.g.
 *  metrics_cost_micros of 46980000 means $46.98. Detect that from the
 *  column name and scale it back to normal currency automatically. */
function unitScale(header: string): number {
  return /micros?\b/i.test(header) ? 1e-6 : 1;
}

/** Human-readable notes about any unit conversions applied, so the user can
 *  see that a "_micros" column was detected and rescaled rather than being
 *  silently 1,000,000x off. */
export function unitConversionNotes(mapping: Record<string, string>): string[] {
  const notes: string[] = [];
  (["spend", "revenue", "sessions"] as const).forEach((field) => {
    const header = mapping[field];
    if (header && unitScale(header) !== 1) {
      notes.push(`"${header}" is in micro-units — divided by 1,000,000 automatically to get standard currency.`);
    }
  });
  return notes;
}

export function normalizeRows(rows: Record<string, any>[], mapping: Record<string, string>): ForecastData[] {
  const spendScale = unitScale(mapping.spend);
  const revenueScale = unitScale(mapping.revenue);
  const sessionsScale = mapping.sessions ? unitScale(mapping.sessions) : 1;
  return rows
    .map((r) => {
      const date = new Date(r[mapping.date]);
      return {
        date: isNaN(date.getTime()) ? null : date.toISOString().slice(0, 10),
        spend: (parseFloat(r[mapping.spend]) || 0) * spendScale,
        revenue: (parseFloat(r[mapping.revenue]) || 0) * revenueScale,
        sessions: mapping.sessions ? (parseFloat(r[mapping.sessions]) || 0) * sessionsScale : 0,
      };
    })
    .filter((r): r is ForecastData => !!r.date && r.revenue >= 0);
}

/**
 * Collapses multiple rows sharing the same date into one daily total. Needed
 * for exports that are broken out by an extra dimension — e.g. one row per
 * campaign per day (Bing/Google Ads campaign reports) — so the forecast
 * engine sees a single clean daily time series instead of duplicate dates.
 */
export function aggregateByDate(data: ForecastData[]): { data: ForecastData[]; wasAggregated: boolean; rawRowCount: number } {
  const map = new Map<string, ForecastData>();
  data.forEach((d) => {
    const cur = map.get(d.date);
    if (cur) {
      cur.spend += d.spend;
      cur.revenue += d.revenue;
      cur.sessions += d.sessions;
    } else {
      map.set(d.date, { ...d });
    }
  });
  const merged = Array.from(map.values()).sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
  return { data: merged, wasAggregated: merged.length < data.length, rawRowCount: data.length };
}

/** Minimal, quote-aware CSV parser (no external dependency required). */
export function parseCSV(text: string): { headers: string[]; rows: Record<string, string>[] } {
  const splitLine = (line: string) => {
    const cells: string[] = [];
    let cur = "";
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
      const c = line[i];
      if (c === '"') {
        inQuotes = !inQuotes;
      } else if (c === "," && !inQuotes) {
        cells.push(cur.trim());
        cur = "";
      } else {
        cur += c;
      }
    }
    cells.push(cur.trim());
    return cells;
  };

  const lines = text.trim().split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (lines.length < 2) return { headers: [], rows: [] };
  const headers = splitLine(lines[0]);
  const rows = lines.slice(1).map((line) => {
    const cells = splitLine(line);
    const row: Record<string, string> = {};
    headers.forEach((h, i) => (row[h] = cells[i] ?? ""));
    return row;
  });
  return { headers, rows };
}

export function toCSV(rows: Record<string, any>[], headers: string[]): string {
  const head = headers.join(",");
  const body = rows.map((r) => headers.map((h) => r[h]).join(",")).join("\n");
  return `${head}\n${body}`;
}

export function downloadFile(content: string, filename: string, type = "text/csv") {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export const fmtMoney = (v: number) => `$${Math.round(v).toLocaleString()}`;
export const todayStamp = () => new Date().toISOString().slice(0, 10);

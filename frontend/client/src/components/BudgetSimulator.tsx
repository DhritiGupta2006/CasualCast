import { useEffect, useState } from "react";
import { Loader2, SlidersHorizontal } from "lucide-react";
import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from "recharts";
import { Slider } from "@/components/ui/slider";
import { simulateBudget, ApiError, type SimulateBudgetResponse } from "@/lib/api";
import type { ForecastData } from "@/lib/forecast";
import { fmtMoney } from "@/lib/forecast";

const MULTIPLIERS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0];

function SliderTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs font-mono-data">
      <div className="mb-1 text-muted-foreground/70">{label}</div>
      <div style={{ color: "var(--chart-1)" }}>Predicted revenue: {fmtMoney(row.predicted_daily_revenue)}</div>
      <div className="text-muted-foreground">ROAS: {row.predicted_roas.toFixed(2)}x</div>
    </div>
  );
}

/**
 * BudgetSimulator — "what if I spent more/less?" slider.
 *
 * The slider itself only picks a spend multiplier; every predicted number
 * shown (revenue, ROAS, deltas) comes straight from
 * core.budget_response via POST /api/simulate-budget. No curve fitting or
 * revenue math happens in this component.
 */
export default function BudgetSimulator({ rows, className = "" }: { rows: ForecastData[]; className?: string }) {
  const [result, setResult] = useState<SimulateBudgetResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [multiplierIdx, setMultiplierIdx] = useState(2); // default 1.0x (baseline)

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    simulateBudget(rows, { multipliers: MULTIPLIERS })
      .then((res) => {
        if (!cancelled) setResult(res);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const detail = err instanceof ApiError ? err.detail : null;
        setError(
          typeof detail === "string"
            ? detail
            : "Couldn't fit a budget-response curve for this data (need at least 7 days with spend > 0)."
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [rows]);

  if (loading) {
    return (
      <div className={`rounded-xl border border-border bg-card p-6 flex items-center gap-2 text-sm text-muted-foreground ${className}`}>
        <Loader2 size={14} className="animate-spin" /> Fitting budget-response curve…
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className={`rounded-xl border border-border bg-card p-6 text-sm text-muted-foreground ${className}`}>
        <div className="flex items-center gap-2 mb-1 text-foreground">
          <SlidersHorizontal size={15} /> Budget simulator
        </div>
        {error || "No budget scenarios available."}
      </div>
    );
  }

  const scenario = result.scenarios[multiplierIdx] ?? result.scenarios[Math.floor(result.scenarios.length / 2)];
  const multiplier = MULTIPLIERS[multiplierIdx] ?? 1;

  return (
    <div className={`rounded-xl border border-border bg-card p-6 ${className}`}>
      <div className="flex items-center gap-2 mb-1 text-sm font-medium text-foreground">
        <SlidersHorizontal size={15} className="text-primary" /> Budget simulator
      </div>
      <div className="text-xs text-muted-foreground mb-5">
        Baseline daily spend {fmtMoney(result.baseline_spend)} → predicted {fmtMoney(result.baseline_predicted_revenue)}
        /day. Drag to explore other spend levels.
      </div>

      <div className="grid sm:grid-cols-3 gap-4 mb-5">
        <div>
          <div className="text-xs uppercase tracking-wider mb-1 text-muted-foreground/70 font-mono-data">Daily spend</div>
          <div className="text-xl font-semibold font-mono-data text-foreground">{fmtMoney(scenario.daily_spend)}</div>
          <div className="text-xs text-muted-foreground">
            {scenario.delta_spend_pct >= 0 ? "+" : ""}
            {scenario.delta_spend_pct}% vs. baseline
          </div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wider mb-1 text-muted-foreground/70 font-mono-data">Predicted revenue</div>
          <div className="text-xl font-semibold font-mono-data text-foreground">{fmtMoney(scenario.predicted_daily_revenue)}</div>
          <div className="text-xs text-muted-foreground">
            {scenario.delta_revenue_pct >= 0 ? "+" : ""}
            {scenario.delta_revenue_pct}% vs. baseline
          </div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wider mb-1 text-muted-foreground/70 font-mono-data">Predicted ROAS</div>
          <div className="text-xl font-semibold font-mono-data text-foreground">{scenario.predicted_roas.toFixed(2)}x</div>
        </div>
      </div>

      <Slider
        min={0}
        max={MULTIPLIERS.length - 1}
        step={1}
        value={[multiplierIdx]}
        onValueChange={([v]) => setMultiplierIdx(v)}
        className="mb-2"
      />
      <div className="flex justify-between text-[10px] text-muted-foreground/60 font-mono-data mb-6">
        {MULTIPLIERS.map((m) => (
          <span key={m} className={m === multiplier ? "text-primary" : ""}>
            {m}x
          </span>
        ))}
      </div>

      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart data={result.scenarios} margin={{ left: -12 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
          <XAxis
            dataKey="daily_spend"
            tickFormatter={(v) => `$${Math.round(v / 100) / 10}k`}
            tick={{ fill: "var(--muted-foreground)", fontSize: 10 }}
            tickLine={false}
            axisLine={{ stroke: "var(--border)" }}
          />
          <YAxis
            tick={{ fill: "var(--muted-foreground)", fontSize: 10 }}
            tickLine={false}
            axisLine={{ stroke: "var(--border)" }}
            tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
          />
          <Tooltip content={<SliderTooltip />} />
          <ReferenceLine x={scenario.daily_spend} stroke="var(--primary)" strokeDasharray="4 3" />
          <Bar dataKey="predicted_daily_revenue" fill="var(--chart-1)" fillOpacity={0.35} radius={[3, 3, 0, 0]} />
          <Line type="monotone" dataKey="predicted_daily_revenue" stroke="var(--chart-1)" strokeWidth={2} dot={false} />
        </ComposedChart>
      </ResponsiveContainer>

      <div className="text-xs text-muted-foreground/70 mt-4">
        Curve fit: R² {result.curve.r_squared.toFixed(2)} over {result.curve.n_points} days of spend/revenue data.
        Predictions extrapolate a log-linear diminishing-returns model — treat spend levels far outside the
        observed ${Math.round(result.curve.spend_min)}–${Math.round(result.curve.spend_max)}/day range as
        lower-confidence.
      </div>
    </div>
  );
}

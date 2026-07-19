import { Info } from "lucide-react";
import type { IncrementalityApi } from "@/lib/api";

/**
 * IncrementalityBadge
 *
 * Renders an incrementality-fraction figure computed by
 * core/incrementality/signal.py (via /api/insights). Per the design doc's
 * ground rules, any incrementality figure MUST carry a "directional
 * signal, not proven causation" disclaimer, and that enforcement lives
 * here: this component always renders the disclaimer whenever it renders
 * a figure — there is no code path that shows one without the other.
 */

const CONFIDENCE_STYLES: Record<IncrementalityApi["confidence"], string> = {
  high: "text-primary border-primary/40 bg-primary/10",
  medium: "text-accent border-accent/40 bg-accent/10",
  low: "text-muted-foreground border-border bg-muted/30",
};

export default function IncrementalityBadge({
  incrementality,
  disclaimer,
  className = "",
}: {
  /** Null when the backend couldn't fit a budget-response curve (too little
   *  spend/revenue data) — the component renders a neutral "not available"
   *  state instead of a figure in that case. */
  incrementality: IncrementalityApi | null;
  /** Fallback disclaimer text if `incrementality.disclaimer` is missing.
   *  Always sourced from the API (core.incrementality.signal.INCREMENTALITY_DISCLAIMER),
   *  never hardcoded independently here. */
  disclaimer?: string;
  className?: string;
}) {
  const text = incrementality?.disclaimer || disclaimer || "Directional signal, not proven causation";

  if (!incrementality) {
    return (
      <div className={`rounded-xl border border-border bg-card p-5 ${className}`}>
        <div className="text-xs uppercase tracking-wider mb-2 text-muted-foreground/70 font-mono-data">
          Incrementality
        </div>
        <div className="text-sm text-muted-foreground">
          Not enough spend/revenue data to estimate an incrementality signal (need at least 7 days with spend
          &gt; 0).
        </div>
      </div>
    );
  }

  const pct = Math.round(incrementality.incrementality_fraction * 100);

  return (
    <div className={`rounded-xl border border-border bg-card p-5 ${className}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="text-xs uppercase tracking-wider text-muted-foreground/70 font-mono-data">
          Incrementality
        </div>
        <span
          className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full border font-mono-data ${CONFIDENCE_STYLES[incrementality.confidence]}`}
        >
          {incrementality.confidence} confidence
        </span>
      </div>

      <div className="text-2xl font-semibold font-mono-data text-foreground mb-1">{pct}%</div>
      <div className="text-xs text-muted-foreground mb-3">
        of avg daily revenue (${incrementality.avg_actual_revenue.toLocaleString()}) looks incremental to spend —
        est. ${incrementality.incremental_revenue.toLocaleString()}/day above a ${incrementality.baseline_revenue.toLocaleString()}/day baseline.
      </div>

      {incrementality.baseline_extrapolated && (
        <div className="text-xs text-muted-foreground/90 bg-muted/30 border border-border rounded-md px-2.5 py-2 mb-3">
          Your daily spend never gets close to $0 in this data, so this baseline is extrapolated well outside
          the observed range — treat it as a rough upper bound, not a precise estimate. That's why confidence
          is capped at &ldquo;low&rdquo; here.
        </div>
      )}

      {/* Mandatory disclaimer — always rendered alongside the figure above. */}
      <div className="flex items-start gap-1.5 text-xs text-muted-foreground/80 border-t border-border pt-3">
        <Info size={13} className="shrink-0 mt-0.5 text-muted-foreground/60" />
        <span>
          <strong className="text-foreground/80">{text}.</strong> This is a statistical signal derived from a
          fitted spend→revenue curve, not a controlled experiment — it does not prove that spend caused this
          revenue.
        </span>
      </div>
    </div>
  );
}

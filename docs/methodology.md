# Methodology

This document explains what each number CausalCast produces actually
means statistically, and — most importantly — where a figure could be
misread as proof of causation when it isn't.

## Ground truth and scope

CausalCast treats whatever conversion data it's given (GA4, Shopify,
Google/Bing/Meta ad-platform exports, or anything with recognizable
date/spend/revenue-like columns) as ground truth. It does not build a
custom attribution model and does not attempt a full media-mix model
(MMM). If two platforms report conflicting numbers for the same
conversion, CausalCast has no opinion about which is "more correct" — it
forecasts and analyzes whatever series it's handed.

## What each `core/` stage actually computes

**Forecast (P10/P50/P90).** `core.forecasting.engine.forecast()` fits an
ordinary-least-squares linear trend to historical revenue, adds a
weekday-seasonality offset (computed only when at least 14 days of
history are available; otherwise seasonality is neutral), and Monte
Carlo-simulates 1,000 (default) future paths by adding seeded Gaussian
noise drawn from the historical residual standard deviation. P10/P50/P90
are the 10th/50th/90th percentiles across those simulated paths at each
future day. **This is a statistical projection of the observed trend and
its historical volatility — it is not aware of upcoming campaigns,
seasonality events outside the training window, or anything that hasn't
already shown up in the historical data.**

**Budget-response curve.** `core.budget_response.fit.fit_response_curve()`
fits `revenue = a·ln(spend + 1) + b` to daily (spend, revenue) pairs by
OLS. This functional form encodes an assumption — diminishing returns to
spend — that is common in ad-response modeling, but it is a modeling
choice, not something derived from the data itself. A dataset where
revenue doesn't actually follow a logarithmic response to spend (e.g. a
step-function launch effect, or a channel that's budget-capped rather
than demand-capped) will still get a log-linear fit; the `r_squared` and
`n_points` fields in the response are the honest signal of how well that
assumption held for this particular dataset. Callers should treat a low
R² or a small `n_points` as a reason to trust the resulting curve less,
not as noise to ignore.

**Budget scenarios.** `core.budget_response.predict.simulate_budget_scenarios()`
evaluates the fitted curve at hypothetical spend multipliers (0.5×, 0.75×,
1×, 1.25×, 1.5×, 2× baseline by default). These are "what would this curve
predict at this spend level," not "what will happen if you actually change
spend" — the curve was fit on a historical range of spend values, and
extrapolating far outside that observed range (`spend_min`/`spend_max` in
the response) is on shakier ground the further out you go.

## Incrementality — the figure most likely to be read as causal

`core.incrementality.signal.estimate_incrementality()` computes:

1. `baseline_revenue` = the fitted response curve's prediction *at zero
   spend* (i.e. the curve's intercept, floored at 0).
2. `incremental_revenue` = average observed daily revenue − `baseline_revenue`.
3. `incrementality_fraction` = `incremental_revenue` / average observed
   daily revenue.
4. `confidence` (`high`/`medium`/`low`) — a heuristic combining the
   response curve's R² and its sample size, *not* a statistical
   confidence interval in the formal sense — **and then forced down to
   `low` whenever `baseline_extrapolated` is true (see below), regardless
   of how good the in-range R² is.**
5. `baseline_extrapolated` (bool) — true when spend = 0 sits far outside
   the spend range the curve was actually fit on (specifically: the
   log-distance from 0 to the observed minimum spend is at least as large
   as the log-width of the observed spend range itself). Real always-on ad
   spend almost never includes near-zero days, so this is the common case,
   not the exception — a campaign that spends $700-$1,000/day every day
   gives the curve nothing to anchor its "revenue at $0/day" prediction on.
   Left unchecked, that extrapolation is free to land anywhere, frequently
   goes negative, gets floored at 0, and silently produces a maxed-out
   100%-incremental, "high confidence" reading no matter what the actual
   spend/revenue relationship looks like — which is the opposite of a
   *directional* signal. When `baseline_extrapolated` is true, treat
   `baseline_revenue` and `incrementality_fraction` as a rough upper bound
   on the answer, not a point estimate: confidence is reported as `low`
   precisely because the number is not to be trusted at face value.

**Why this is a correlational estimate, not a causal one.** The whole
calculation rests on the same OLS curve described above — it reads
"what revenue level does the curve associate with zero spend," and calls
the gap between that and actual revenue "incremental." That's a
reasonable directional signal when spend and revenue move together in the
data, but nothing here rules out confounding: revenue could be rising for
reasons unrelated to spend (a seasonal trend, a pricing change, organic
growth) while spend also happens to be rising, which would inflate the
apparent incrementality fraction without spend actually causing any of
that lift. Conversely, a channel could be genuinely incremental in a way
this method understates if spend and revenue are recorded at different
levels of temporal granularity than the response curve assumes. Proving
causation would require a controlled experiment (geo holdout, PSA test,
conversion lift study) — CausalCast explicitly does not run one and does
not claim to.

**Where the disclaimer is enforced, not just written down.** The exact
string `"Directional signal, not proven causation"` is defined once, in
`core.incrementality.signal.INCREMENTALITY_DISCLAIMER`, and every other
place that touches this figure imports that constant rather than
re-typing it:

- `IncrementalityResult.disclaimer` (`core/incrementality/signal.py`)
  defaults to it and is included in every `to_dict()` payload.
- `backend/api/routes/insights.py` re-exports it as
  `incrementality_disclaimer` in the `/api/insights` response, alongside
  the per-result `incrementality.disclaimer` field.
- `backend/llm/prompt_template.py`'s `SYSTEM_PROMPT` instructs the model
  that, whenever an incrementality figure is present, its narration
  *must* include this exact sentence verbatim — and
  `ensure_disclaimer()` checks the model's output afterward and appends
  the disclaimer if the model failed to include it, so the enforcement
  doesn't depend on the model following instructions correctly.
- `src/predict.py` writes it into the `incrementality_disclaimer` column
  of `output/predictions.csv` on every row that has an incrementality
  estimate, so the disclaimer travels with the figure even in the
  scored, non-interactive pipeline output.
- `frontend/client/src/components/IncrementalityBadge.tsx` has no code
  path that renders the incrementality percentage without also rendering
  this disclaimer text underneath it — the two are in the same
  component return block, not separately toggleable.

## Anomalies

`core.preprocessing.anomalies.flag_anomalies()` uses a Tukey IQR fence
(1.5× IQR beyond Q1/Q3 by default) rather than a Z-score, because Z-scores
assume a roughly normal distribution and can be distorted by the very
outliers they're trying to detect, especially on the short time series
this tool is designed for (fewer than 7 rows: nothing is flagged, since
there isn't enough data to distinguish an outlier from noise). Flagged
days are *not* removed from the forecast — they're counted and surfaced as
a warning, since a real spend/revenue spike (a promotion, a stockout) is
often exactly the kind of day a marketer cares about, not noise to
discard silently.

## Confidence bands are historical, not predictive of the unknown

The P10/P90 forecast band width reflects how volatile the *historical*
residuals were — it does not know about anything that hasn't happened yet
(a planned budget change, a competitor's move, a holiday outside the
training window). A narrow band means the recent past was consistent, not
that the future is guaranteed to be.

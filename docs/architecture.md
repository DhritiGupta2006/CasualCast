# Architecture

CausalCast is one shared forecasting library (`core/`) consumed by two
independent artifacts that are judged differently. This document exists so
a judge — or anyone else reading the repo — understands why those two
artifacts look different and why that's intentional, not a leftover from
an unfinished merge.

## The two tracks

| | **Scored pipeline** | **Live demo** |
|---|---|---|
| Entry point | `run.sh` → `src/generate_features.py` → `src/predict.py` | `backend/api/main.py` (FastAPI) + `frontend/` (React) |
| Runs on | The organizers' clean clone, offline | This machine, for judges, online |
| Network access | None — `core/` and `src/` never import `requests`, `httpx`, or an LLM SDK | Full — `backend/llm/` calls the Anthropic API |
| Model | Pre-trained `pickle/model.pkl`, committed. `src/train.py` produced it but is never called by `run.sh` | No pickle — every request re-fits/re-forecasts from the rows it's given |
| Output | `output/predictions.csv`, one file, overwritten each run | JSON responses from `/api/forecast`, `/api/simulate-budget`, `/api/insights` |
| Judged on | Pass/fail correctness of the CSV | Practical relevance, AI integration, product thinking |

Both tracks import `core/` and nothing else for their numbers. That is
the whole point of the split: `src/predict.py` calls
`core.forecasting.engine.forecast`, `core.budget_response`, and
`core.incrementality.signal` directly; `backend/api/routes/forecast.py`
calls the identical functions (via `core.rollup.orchestrator.run_pipeline`)
on the same input. Given the same rows, horizon, iterations, and seed,
the two tracks cannot diverge, because they bottom out in the same
deterministic code — neither one has its own copy of the math.

```
┌───────────────────────────────────────────────────────────────────┐
│  core/  — shared, network-free forecasting library                │
│                                                                     │
│  ingestion → preprocessing → forecasting → budget_response         │
│              → incrementality → rollup                             │
│                                                                     │
│  No requests/httpx/LLM SDK imports anywhere in this tree.          │
│  No absolute paths — every function takes paths/DataFrames in.     │
│  Every stochastic step (Monte Carlo, bootstrap CI) takes an        │
│  explicit seed, defaulted to 42.                                   │
└───────────────┬─────────────────────────────────┬─────────────────┘
                │                                 │
     scored, offline, batch             live, online, interactive
                │                                 │
                ▼                                 ▼
┌───────────────────────────────┐   ┌─────────────────────────────────┐
│ src/  (+ run.sh, pickle/)      │   │ backend/  (FastAPI)             │
│                                │   │                                 │
│ generate_features.py           │   │ api/routes/upload.py            │
│   → core.ingestion,            │   │   → core.ingestion + preprocess │
│     core.preprocessing         │   │ api/routes/forecast.py          │
│ predict.py                     │   │   → core.rollup.orchestrator    │
│   → loads model.pkl, calls     │   │ api/routes/simulate_budget.py   │
│     core.forecasting,          │   │   → core.budget_response        │
│     core.budget_response,      │   │ api/routes/insights.py          │
│     core.incrementality        │   │   → core.rollup.orchestrator    │
│   → writes predictions.csv     │   │     + backend/llm (narration)   │
│ train.py                       │   │                                 │
│   → NOT in run.sh's call path; │   │ llm/summarizer.py                │
│     shows how model.pkl was    │   │   → Anthropic API, with a       │
│     produced, for              │   │     template-fallback path      │
│     reproducibility only       │   │     that never blocks the demo  │
└────────────────────────────────┘   └──────────────┬──────────────────┘
                                                     │
                                                     ▼
                                     ┌─────────────────────────────────┐
                                     │ frontend/  (React, from the     │
                                     │ original causalcast.zip)        │
                                     │                                 │
                                     │ lib/api.ts — calls backend/api  │
                                     │ Forecast.tsx — upload, chart,   │
                                     │   IncrementalityBadge,          │
                                     │   BudgetSimulator               │
                                     │                                 │
                                     │ Never computes a forecast       │
                                     │ number itself — only shapes     │
                                     │ what the API already returned.  │
                                     └─────────────────────────────────┘
```

## `core/` module order and responsibilities

The six `core/` packages are built and tested in dependency order — each
one is what the next one needs:

1. **`core/ingestion/`** (`loaders.py`, `schema.py`) — reads CSVs (a
   single file or every `*.csv` in a directory), renames GA4/Shopify/
   ad-platform-specific column headers to a canonical schema
   (`date`, `spend`, `revenue`, `sessions`, `channel`), detects and
   rescales Google Ads-style `_micros` columns, strips currency symbols,
   and validates that `date`/`spend`/`revenue` are present and parseable.
2. **`core/preprocessing/`** — `taxonomy.py` classifies raw channel/source
   strings (e.g. `"google / cpc"`, `"fb_ads"`) into a small fixed set of
   channel groups (Paid Search, Paid Social, Organic Search, Email, …);
   `anomalies.py` flags or Winsorizes outlier days using an IQR fence
   (not a trained model, so it works even on very small datasets);
   `seasonality.py` computes per-weekday multiplicative/additive factors,
   falling back to neutral factors when there's under two weeks of data.
3. **`core/forecasting/`** — `trend_decomposition.py` fits an OLS linear
   trend and computes residual volatility; `monte_carlo.py` simulates many
   future paths (trend + weekday seasonality + seeded Gaussian noise,
   floored at zero since revenue can't be negative) and extracts P10/P50/
   P90 bands; `engine.py` is the single public `forecast()` entry point
   that wires the two together and adds summary stats (trend direction,
   confidence-range %).
4. **`core/budget_response/`** — `fit.py` fits `revenue = a·ln(spend+1) + b`
   by OLS (captures diminishing returns without needing the data volume a
   Hill/Michaelis–Menten curve would need), with an optional seeded
   bootstrap for a 90% CI on `a`; `predict.py` evaluates that curve at
   hypothetical spend levels for the budget-slider "what-if" table.
5. **`core/incrementality/`** — `signal.py` estimates a *directional*
   incrementality fraction: `baseline` = the response curve's predicted
   revenue at zero spend, `incremental` = observed average revenue minus
   that baseline. Confidence (`high`/`medium`/`low`) comes from the
   curve's R² and sample size. This is the one number in the whole system
   that's easiest to misread as causal — see `methodology.md`.
6. **`core/rollup/`** — `orchestrator.py`'s `run_pipeline()` runs all five
   stages in order and returns one `PipelineResult` object. Both
   `backend/api/routes/forecast.py`/`insights.py` and (indirectly, via the
   same underlying calls) `src/predict.py` build on this so there's one
   orchestration path, not two copies of "what order do we call things in."

## Why the frontend doesn't compute anything

`lib/api.ts` only shapes HTTP requests/responses; `Forecast.tsx` and
`BudgetSimulator.tsx` only render whatever `/api/forecast`,
`/api/simulate-budget`, and `/api/insights` returned. The one piece of
client-side logic that *looks* like computation — CSV column mapping
(matching an uploaded header like `"Sales"` to the `revenue` field) — is
UI convenience for previewing the mapping before submission; the actual
canonicalization (currency stripping, micros scaling, type coercion) is
the same `core.ingestion.schema` code the backend and batch pipeline use,
run again server-side once rows are submitted to `/api/forecast` or
`/api/insights`.

`backend/api/routes/upload.py` also exposes a `POST /api/upload` endpoint
that runs a raw CSV through the same ingestion/preprocessing steps
server-side and returns cleaned rows — built for any client that wants to
hand over a raw file instead of already-parsed rows. The current
`Forecast.tsx` flow parses/maps columns in the browser and posts rows
directly to `/api/forecast`/`/api/insights`, so this route isn't on the
demo's click path today; it's available for a file-upload flow without
requiring UI changes.

## One-directional dependency

`backend/` imports `core/`. `core/` never imports anything from
`backend/` or `src/`. `src/` imports `core/` the same way `backend/` does.
Nothing in `core/` knows FastAPI, JSON, or HTTP exist, and nothing in
`core/` knows the Anthropic SDK exists — that's what makes it safe to
import from a zero-network batch script and a live networked API with the
exact same behavior in both places.

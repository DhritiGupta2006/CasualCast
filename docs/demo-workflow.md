# Demo workflow

This is the actual click-through path for the live demo — what a judge
sees, in order, when the FastAPI backend and React frontend are both
running. It does not cover `run.sh` / `predictions.csv`; that's the
scored batch pipeline, described in `architecture.md` and the root
`README.md`.

## 1. Start both halves

```bash
# Terminal 1 — backend
pip install -r backend/requirements-backend.txt
uvicorn backend.api.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
pnpm install   # or npm install
pnpm dev       # or npm run dev
```

The frontend calls the backend at `http://localhost:8000` by default
(configurable via `VITE_API_BASE_URL` in `frontend/.env`). `GET /health`
on the backend returns `{"status": "ok"}` once it's up.

## 2. Home → Forecaster

The app has two routes: `/` (`Home`, a landing page) and `/forecast`
(`Forecast`, where the actual demo lives). Click through to the
forecaster.

## 3. Get data in

`Forecast.tsx` offers three ways to provide daily spend/revenue history,
side by side:

- **Drag-and-drop or browse for a file** — accepts `.csv`, `.xlsx`, `.xls`.
- **Paste CSV text directly** into a textbox and click "Parse pasted data."
- **"Load sample data"** — a one-click canned dataset, useful for a quick
  demo pass without needing a real file on hand.
- ("Download CSV template" is also available if a judge wants to see the
  expected shape before providing their own data.)

Column mapping (matching whatever headers the file has — `"Sales"`,
`"Total Cost"`, etc. — to the canonical `date` / `spend` / `revenue` /
`sessions` fields) happens client-side for preview, and can be adjusted
manually via "Adjust columns" if the automatic detection guesses wrong.
The actual cleaning (currency-symbol stripping, micros-unit detection,
type coercion) happens again server-side, via the same
`core.ingestion.schema` functions used everywhere else, once data is
submitted.

## 4. Generate forecast

Once `date`, `spend`, and `revenue` are mapped, clicking **"Generate
forecast"** calls `runForecast()` in `lib/api.ts`, which `POST`s the
mapped rows to `/api/forecast`. That route runs the full
`core.rollup.orchestrator.run_pipeline()` — the same call
`src/predict.py` makes for the batch pipeline — and returns:

- Per-day P10/P50/P90 revenue bands
- Summary stats (trend direction, slope, confidence-range %)
- Anomaly count, detected channel groups, weekday factors
- Any ingestion notes/warnings (e.g. a detected micros-unit conversion)

## 5. Chart renders

The forecast response feeds directly into a composed chart: historical
daily revenue on the left, the P10/P50/P90 band continuing forward from
the last historical day. Nothing is computed in the chart component
itself — it only plots `results` and `historical` exactly as the API
returned them.

## 6. Incrementality badge

Once a forecast exists, `getInsights()` is called against `/api/insights`,
which runs the same pipeline plus incrementality estimation and hands the
numeric payload to `backend/llm/summarizer.narrate()` for prose narration.
`IncrementalityBadge.tsx` then renders:

- The incrementality percentage and confidence level (or a "not enough
  data" state if a response curve couldn't be fit — needs ≥7 days with
  spend > 0)
- The mandatory **"Directional signal, not proven causation"** disclaimer,
  always shown alongside the figure, never separately

## 7. Budget simulator

`BudgetSimulator.tsx` calls `simulateBudget()` against
`/api/simulate-budget` with the same rows, showing a table of predicted
revenue/ROAS at different hypothetical daily spend levels (0.5×–2× the
observed average, by default). This route deliberately skips the full
Monte Carlo forecast — it only needs the cheap, deterministic budget-
response curve — so it can respond fast enough for a slider to hit it
repeatedly.

## 8. Narration fallback (worth demonstrating deliberately)

If `ANTHROPIC_API_KEY` is unset (or the call fails for any reason),
`/api/insights` still returns a complete response — `template_summary`
is built by `backend/llm/prompt_template.build_template_summary()`
instead of an LLM call, and `narration_source` reports `"template"`
rather than `"llm"`. A good way to demonstrate resilience live: kill the
API key mid-demo (or just don't set it) and show the insight panel still
renders correctly, just with template prose instead of Claude-narrated
prose. None of the numeric surfaces (forecast chart, budget table,
incrementality figure) depend on this call succeeding either way.

## What's intentionally not on this path

`POST /api/upload` exists on the backend (parses a raw CSV file
server-side using the same ingestion/preprocessing core functions) but
isn't currently called by `Forecast.tsx`, which does its own client-side
parsing and column mapping before submitting rows directly to
`/api/forecast`/`/api/insights`. It's there for a client that wants to
hand over an unparsed file rather than pre-mapped rows.

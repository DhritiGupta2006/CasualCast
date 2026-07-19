# CausalCast

Marketing-analytics forecasting: daily revenue projections, a
budget-response curve, and a directional incrementality signal, computed
by one shared, network-free library (`core/`) and consumed by two
separate artifacts — a scored offline batch pipeline and a live demo.

## The pipeline-vs-demo split

CausalCast ships two things that share the same math but run under very
different constraints:

- **Scored pipeline** (`run.sh`, `src/`, `pickle/model.pkl`) — what the
  organizers' automated grading actually runs. No network access, no
  retraining, no LLM. Loads a pre-trained model and writes
  `output/predictions.csv`. This is what must work cleanly on a fresh
  clone with nothing but `pip install -r requirements.txt`.
- **Live demo** (`backend/` FastAPI app + `frontend/` React app) — what a
  judge sees interactively: upload data, watch a forecast chart render,
  drag a budget slider, read an LLM-narrated (or template-narrated,
  key-optional) insight panel.

Both call the exact same `core/` functions on the same input, so the two
can never report different numbers for the same data. See
`docs/architecture.md` for the full breakdown, `docs/methodology.md` for
what each number means (and doesn't mean), and `docs/demo-workflow.md` for
the live-demo click-through path.

## Requirements

- **Python 3.12** (developed and tested against 3.12.3)
- Node.js + pnpm (or npm) — only needed for the `frontend/` live demo,
  not for the scored pipeline

## Running the scored pipeline

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

./run.sh ./data ./pickle/model.pkl ./output/predictions.csv
```

All three arguments are positional and optional — the command above uses
the defaults, so `./run.sh` alone does the same thing. `run.sh` never
retrains (`src/train.py` produced the committed `pickle/model.pkl` and is
not in this call path); it only runs `src/generate_features.py` followed
by `src/predict.py`, both of which read local files and call `core/` —
zero network access, no other setup beyond the `pip install` above.

Output: `output/predictions.csv`, written fresh every run (never
appended), with per-day `revenue_p10`/`revenue_p50`/`revenue_p90`, trend
direction/slope, a baseline-spend/predicted-ROAS pair, and an
incrementality fraction/confidence/disclaimer.

To reproduce `pickle/model.pkl` from scratch (not required to run the
pipeline — it's already committed):

```bash
python src/train.py ./data ./pickle/model.pkl
```

## Running the tests

```bash
pip install -r requirements.txt pytest
python -m pytest tests/ -q
```

Covers each `core/` module individually, the end-to-end `run.sh` flow
(including a determinism check — identical input must produce a
byte-identical `predictions.csv`), and that `requirements.txt` stays free
of backend-only dependencies.

## Running the live demo

```bash
# backend
pip install -r backend/requirements-backend.txt
cp backend/.env.example backend/.env   # optional — set ANTHROPIC_API_KEY to enable LLM narration
uvicorn backend.api.main:app --reload --port 8000

# frontend, in a second terminal
cd frontend
pnpm install
pnpm dev
```

The LLM narration layer degrades to a deterministic template summary if
`ANTHROPIC_API_KEY` is unset or the API call fails for any reason — the
forecast chart, budget simulator, and incrementality figure never depend
on it.

## Repo layout

```
run.sh                    # scored-pipeline entrypoint (root, executable)
requirements.txt          # pinned deps for core/ + src/ only
data/                     # sample input CSVs
pickle/model.pkl          # pre-trained, committed model
output/                   # run.sh writes predictions.csv here
src/                      # thin pipeline scripts, wrap core/
core/                     # shared, network-free forecasting library
tests/                    # per-module tests + end-to-end pipeline test
backend/                  # FastAPI live API + LLM narration layer
frontend/                 # React demo UI (moved from the original zip)
docs/                     # architecture, methodology, demo-workflow (this folder)
```

## Team

_Team name, members, and college — fill in before submission._

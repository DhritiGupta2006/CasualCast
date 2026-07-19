# CausalCast — Combined Build Design Document (v2)
## Existing React Frontend + FastAPI Live Backend + Scored Batch Pipeline
### Verified against `causalcast.zip`, the AIgnition 3.0 problem statement, and the Hackathon Submission Guide

**What changed in v2:** The Submission Guide makes clear that what gets *automatically scored* is not the live product — it's a `run.sh` → pickle → CSV batch pipeline with **no network access at run time**. This means the LLM causal-insights layer, and the live FastAPI/React product generally, are not part of the graded artifact. v2 splits the project into two tracks sharing one core forecasting library, so nothing about the live-product design from v1 is wasted — it's just no longer the thing being scored.

---

## 1. The two tracks

| | **Scored pipeline** | **Live demo** |
|---|---|---|
| What it is | `run.sh`, `src/`, `pickle/model.pkl` | React frontend + FastAPI backend |
| Who/what runs it | The organizers' automated pipeline, on a clean clone, with their held-out data | You, live, for judges |
| Network access | **None allowed at run time** | Full — LLM API calls, live uploads |
| LLM involved? | **No** | Yes — narration/causal-summary layer |
| Judged by | Pass/fail correctness of `output/predictions.csv` | Practical Relevance, AI Integration, Product Thinking criteria |
| Failure mode | Zero for that run if anything requires manual fixing | Subjective — a rough demo still scores something |

Both tracks import the same `core/` forecasting library. `src/predict.py` loads a **pre-trained, already-pickled** model and calls `core/` functions in batch mode. `backend/api/routes/forecast.py` calls the same `core/` functions in live mode, then optionally hands the numeric result to `backend/llm/` for narration. This is what keeps the two tracks numerically consistent — a judge who compares your live demo's numbers to your pipeline's `predictions.csv` on the same data should not see a discrepancy.

---

## 2. Non-negotiable constraints (updated)

1. All forecasting math is deterministic and inspectable, computed before any LLM call — LLM never computes or alters a number.
2. `core/` has **zero import-time or call-time network dependency**. Nothing in `core/` may call `requests`, `httpx`, an LLM SDK, or fetch anything from a URL. Network calls exist only in `backend/llm/` and `backend/api/`, which the scored pipeline never imports.
3. **`src/predict.py` must run with zero internet access.** No downloading weights, no calling an API, no pulling a lookup table from a URL. Anything the model needs (fitted parameters, seasonality indices, budget-response curve coefficients) is baked into `pickle/model.pkl` at training time.
4. Model must be **pre-trained and committed** — `run.sh` does not retrain. `src/train.py` exists for reproducibility and for judges reading your code, but it is not in the pipeline's call path.
5. Every random process in the scored path (Monte Carlo residual resampling, any stochastic budget-response fit) must be seeded. Same input in `data/` → same `output/predictions.csv`, every run.
6. Existing platform-reported attribution (GA4 / Shopify / ad-platform conversion data) is treated as ground truth; no custom attribution model, no full MMM — matches the problem statement's explicit scope limit.
7. Incrementality figures always carry the "directional signal, not proven causation" disclaimer — enforced in the frontend (`IncrementalityBadge.tsx`) and, where the pipeline outputs an incrementality column, documented in `docs/methodology.md` rather than silently presented as causal.
8. The frontend never computes forecasts itself — only the API (live) or `src/predict.py` (batch) produce numbers.
9. No absolute paths anywhere in `core/` or `src/`. Only the three arguments `run.sh` passes down, or paths relative to them.

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  core/  — shared, network-free forecasting library                  │
│  ingestion → preprocessing → forecasting → budget_response          │
│  → incrementality → rollup                                          │
│  (imported by BOTH branches below; contains no LLM code, no I/O     │
│   beyond reading files it's explicitly given a path to)             │
└───────────────┬───────────────────────────────────┬─────────────────┘
                │                                   │
   scored, offline, batch              live, online, interactive
                │                                   │
                ▼                                   ▼
┌───────────────────────────────┐   ┌─────────────────────────────────┐
│  src/  (+ run.sh, pickle/)     │   │  backend/  (FastAPI)            │
│  generate_features.py          │   │  api/routes/*  → calls core/    │
│  predict.py — loads model.pkl, │   │  llm/ — Anthropic API, ONLY     │
│    calls core/, writes CSV     │   │    live-side, narrates numbers  │
│  train.py — how model.pkl was  │   │    core/ already computed      │
│    produced (not in run path)  │   └──────────────┬──────────────────┘
└────────────────────────────────┘                  │
                                                      ▼
                                     ┌─────────────────────────────────┐
                                     │  frontend/  (React, from zip)   │
                                     │  upload, charts, budget sliders,│
                                     │  insight panel                  │
                                     └─────────────────────────────────┘
```

---

## 4. Folder structure to hand to Antigravity

```
causalcast/                          # repo root
├── run.sh                           # REQUIRED by submission guide — root, exact name
├── requirements.txt                 # REQUIRED — pinned versions, root of repo
├── data/                            # REQUIRED — sample CSVs; org's pipeline overwrites this
│   └── sample_ga4_shopify_ads.csv   # small, committed, real schema
├── pickle/
│   └── model.pkl                    # REQUIRED — pre-trained, committed, loads with pinned versions
├── output/
│   └── .gitkeep                     # run.sh writes predictions.csv here; gitignore the CSV itself
├── src/                             # REQUIRED — pipeline entry scripts only, thin wrappers over core/
│   ├── generate_features.py
│   ├── predict.py
│   └── train.py                     # not called by run.sh; how model.pkl was produced
│
├── core/                            # NEW — shared library, no network code, imported by src/ AND backend/
│   ├── __init__.py
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── loaders.py
│   │   └── schema.py
│   ├── preprocessing/
│   │   ├── __init__.py
│   │   ├── taxonomy.py
│   │   ├── anomalies.py
│   │   └── seasonality.py
│   ├── forecasting/
│   │   ├── __init__.py
│   │   ├── trend_decomposition.py
│   │   ├── monte_carlo.py
│   │   └── engine.py
│   ├── budget_response/
│   │   ├── __init__.py
│   │   ├── fit.py
│   │   └── predict.py
│   ├── incrementality/
│   │   ├── __init__.py
│   │   └── signal.py
│   └── rollup/
│       ├── __init__.py
│       └── orchestrator.py
│
├── backend/                         # live product only — never imported by src/
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── summarizer.py
│   │   └── prompt_template.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── upload.py
│   │       ├── forecast.py          # imports core/, not src/
│   │       ├── simulate_budget.py
│   │       └── insights.py
│   ├── requirements-backend.txt     # backend+LLM-only deps (fastapi, anthropic sdk, uvicorn)
│   │                                 # kept SEPARATE from root requirements.txt so the scored
│   │                                 # pipeline's pip install never pulls in server/LLM deps
│   └── .env.example
│
├── frontend/                        # existing causalcast/ zip, moved in as-is + refactors (see prior doc)
│   ├── client/...
│   ├── server/index.ts
│   ├── shared/const.ts
│   └── package.json
│
├── tests/
│   ├── test_core_ingestion.py
│   ├── test_core_preprocessing.py
│   ├── test_core_forecasting.py
│   ├── test_core_budget_response.py
│   ├── test_core_incrementality.py
│   ├── test_core_rollup.py
│   ├── test_pipeline_end_to_end.py  # runs run.sh against tests/fixtures/ and checks output shape
│   └── fixtures/
│       └── tiny_sample.csv
│
├── docs/
│   ├── CausalCast_Combined_Build_Design.md   # this document
│   ├── architecture.md
│   ├── methodology.md
│   └── demo-workflow.md
│
├── .gitignore
├── .gitattributes                   # Git LFS tracking line if model.pkl is large
├── README.md                        # states Python version, exact run command, pipeline vs demo split
└── LICENSE
```

**Key structural decision:** `requirements.txt` at the root is what the organizers' `pip install -r requirements.txt` reads — it must contain **only** what `run.sh` needs (pandas, numpy, scikit-learn/statsmodels, whatever `core/` and `src/` import). FastAPI, uvicorn, and the Anthropic SDK go in `backend/requirements-backend.txt` instead, installed separately by you for the live demo, and never touched by the scored pipeline. Mixing them into one `requirements.txt` risks slower/flakier installs on the grading machine and pulls in packages (like an LLM SDK) that have no reason to be near a network-free batch job.

**Instruction to give Antigravity verbatim:**
> "Move the contents of the uploaded `causalcast/` zip into `frontend/` untouched except where section 4 of the v1 design doc marks NEW/REFACTORED. Build `core/` first as a pure, network-free Python library per `docs/CausalCast_Combined_Build_Design.md` §2–3. Build `src/`, `run.sh`, and `train.py` next, and get `tests/test_pipeline_end_to_end.py` passing on a fresh clone before touching `backend/` or the LLM layer. Never import anything from `backend/` into `core/` or `src/`, and never add network-calling packages to the root `requirements.txt`."

---

## 5. `run.sh` — build order and acceptance test

Build and lock this down **first**, before any frontend polish or LLM work, since it's the part that can zero out the submission. Acceptance test: clone the repo into a brand-new directory, `pip install -r requirements.txt` in a fresh venv, run `./run.sh ./data ./pickle/model.pkl ./output/predictions.csv` with **no other setup**, and confirm `output/predictions.csv` exists with the announced columns. Do this on a machine/container that has never had your dev environment on it — your own laptop with node_modules and half-installed packages everywhere is not a valid test.

Stub files are provided below as the actual starting point — see the three files delivered alongside this document (`run.sh`, `src/generate_features.py`, `src/predict.py`, `src/train.py`).

---

## 6. Frontend and live-backend design

Unchanged from v1 — see the "Frontend changes required" and "Backend — Stage responsibilities" sections in your original combined design doc. The only difference: `backend/api/routes/forecast.py` now imports `core.forecasting.engine` rather than a backend-local forecasting module, so the live API and the batch pipeline are guaranteed to use identical math.

---

## 7. Git practices (updated)

Same branching/commit conventions as v1 (§7 of the prior document), with these additions:

- **Branch order changes**: `feat/core-ingestion` → `feat/core-preprocessing` → `feat/core-forecasting` → `feat/core-budget-response` → `feat/core-incrementality` → `feat/core-rollup` → `feat/pipeline-run-sh` (this is the one to get merged and tagged before anything else) → then `feat/backend-api`, `feat/backend-llm`, `feat/frontend-integration`.
- **Tag `v0.1-pipeline`** the moment `run.sh` passes the clean-clone acceptance test above — this is your safety net if you run out of time before the live demo is fully polished; the scored artifact is locked in.
- **`.gitattributes`** — if `pickle/model.pkl` is more than a few MB, add Git LFS tracking (`git lfs track "pickle/*.pkl"`) and confirm the organizers' pipeline can actually pull LFS objects (the guide explicitly warns: "the file must come down with a plain git clone" — if you're not sure their clone step pulls LFS, keep the pickle small enough to commit directly rather than risk it).
- **Repo must be public** at submission time per the guide (§10) — different from the v1 suggestion to keep it private until judging. Reconcile this with the IP-assignment clause in the hackathon T&Cs: submit as public since the guide requires it, understanding NetElixir's T&Cs already claim IP over anything submitted regardless of repo visibility.

---

## 8. Submission-guide compliance checklist (map this to their §9 verbatim)

- [ ] Repo on GitHub, **public**
- [ ] `run.sh` at root, executable, exact filename, runs end-to-end with one invocation
- [ ] `run.sh` accepts `DATA_DIR MODEL_PATH OUTPUT_PATH` positionally, with the recommended defaults
- [ ] `data/` folder present; `src/generate_features.py` reads it dynamically (by documented filename pattern, not hardcoded), never assumes row count
- [ ] `pickle/model.pkl` committed, pre-trained, loads cleanly with the exact versions pinned in root `requirements.txt`
- [ ] Root `requirements.txt` pins every version (`pandas==2.2.2`, not `pandas`) — and contains nothing from `backend/`
- [ ] Output written fresh (not appended) to `OUTPUT_PATH`, columns matching the announced format — **confirm this format with organizers if you can't locate the launch announcement**
- [ ] Seeds set anywhere randomness affects predictions (Monte Carlo, any stochastic fit)
- [ ] No absolute paths anywhere in `core/` or `src/`
- [ ] No network calls anywhere in the call path from `run.sh`
- [ ] Tested on an actual clean clone in a fresh environment, not the dev machine
- [ ] README states Python version and the exact run command
- [ ] Submission email to sunitha.k@netelixir.us by **19 July 2026, 10:00 PM IST**, with repo URL, exact run command, team name/members/college

---

## 9. Hackathon deliverable mapping (updated)

| PS/Guide deliverable | Where it lives |
|---|---|
| 1. Working prototype (PS) | `frontend/` + `backend/`, live, for the demo |
| Scored pipeline (Guide) | `run.sh` + `src/` + `pickle/model.pkl`, offline, for automated grading |
| 2. Technical documentation (PS) | `docs/methodology.md` |
| 3. Architecture overview (PS) | `docs/architecture.md` — should explicitly diagram the two-track split in §1/§3 above, since a judge reading it needs to understand why the demo and the scored artifact are different things |
| 4. Demo workflow (PS) | `docs/demo-workflow.md` |

---

## 10. Revised priority order given the timeline

Deadline is **19 July, 10:00 PM IST** — very little runway left. Priority, in order:

1. `core/` forecasting (Stages ingestion → forecasting, minimum viable) 
2. `src/train.py` to produce a real `pickle/model.pkl`, then `run.sh` + `generate_features.py` + `predict.py` — **get this passing the clean-clone test today**, tag `v0.1-pipeline`
3. Only after (2) is locked: live FastAPI wiring to the same `core/`
4. Frontend integration (`lib/api.ts`, budget sliders, chart wiring)
5. LLM narration layer (`backend/llm/`) — last, lowest risk to the score if it slips, since it's demo-only and already has a template-fallback path
6. `docs/` written last, from what was actually built, not speculated beforehand

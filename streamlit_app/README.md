# CausalCast — Streamlit demo (bonus/alternative UI)

This is an **additional** UI on top of `core/` — it does not replace the
React + FastAPI live demo, and it doesn't touch `run.sh`, `src/`,
`core/`, `backend/`, `frontend/`, `tests/`, or `docs/`. The scored batch
pipeline and the React live demo are unaffected by this folder's
existence.

It computes nothing itself: every number comes from one
`core.rollup.orchestrator.run_pipeline()` call, the same function
`src/predict.py` and `backend/api/routes/forecast.py` use — so this page
can never report different numbers than a batch run of the same data.

## Run it

```bash
pip install -r requirements.txt -r streamlit_app/requirements-streamlit.txt
streamlit run streamlit_app/app.py
```

Opens on `http://localhost:8501`. Use the sidebar to switch between the
committed sample data (`data/sample_data.csv`) and your own CSV upload.

## What it shows

- Revenue forecast (P10/P50/P90) — same Monte Carlo engine as the batch
  pipeline, with adjustable horizon/iterations/seed in the sidebar.
- An interactive budget-response slider (`core.budget_response`).
- The incrementality signal, with the mandatory "directional signal, not
  proven causation" disclaimer always rendered alongside the figure, and
  an explicit warning when the zero-spend baseline is extrapolated far
  outside the observed spend range (mirrors
  `frontend/client/src/components/IncrementalityBadge.tsx`).
- A plain-English summary — deterministic template by default; tick
  "Narrate with LLM" in the sidebar to use `backend/llm/summarizer.py`
  if `ANTHROPIC_API_KEY` is set (falls back to the template automatically
  if it's unset or the call fails, same as the React live demo).

## Dependency note

`streamlit_app/requirements-streamlit.txt` pins `streamlit==1.59.2`
specifically because it's the earliest Streamlit release compatible with
the root `requirements.txt`'s `pandas==3.0.2` pin (Streamlit <1.52 caps
at `pandas<3`). Don't downgrade it without checking that constraint again.

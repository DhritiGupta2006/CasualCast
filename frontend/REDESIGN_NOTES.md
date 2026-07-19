# Redesign notes

This pass replaces the visual design and rebuilds the forecasting engine
inside the original project structure — same stack (React 19 + TS + Vite +
Tailwind 4 + shadcn/ui + Recharts), same routes (`/` and `/forecast`).

## What changed

**Theme (`client/src/index.css`, `client/index.html`)**
- New "instrument panel" palette: graphite background (#0B0E14), signal-green
  primary (#3DDC97), gold upside / soft-blue downside as the forecast-band
  accents. Light-mode fallback tokens included in `:root`.
- Typography swapped to Fraunces (display) + Inter (body) + JetBrains Mono
  (data/numbers), loaded via Google Fonts in `index.html`.
- App now defaults to dark theme (`App.tsx`).

**New shared components**
- `client/src/components/Header.tsx` — sticky nav, mobile menu, wouter routing.
- `client/src/components/Footer.tsx`.
- `client/src/lib/forecast.ts` — the forecasting engine, extracted out of the
  page component so it's typed, testable, and reusable.

**Homepage (`client/src/pages/Home.tsx`)**
- New hero with an animated SVG "probability cone" — a literal picture of a
  P10/P50/P90 fan chart, built as the signature visual instead of a generic
  gradient-and-stats hero.
- Features grid, 4-step method, and an honest "what we claim / don't claim"
  trust section carried over from the original brief's positioning.

**Forecaster (`client/src/pages/Forecast.tsx`)**
- Real Monte Carlo engine (1,000 iterations, linear trend + weekday
  seasonality + residual-volatility noise) replacing the simpler mean/sine
  model — see `lib/forecast.ts`.
- CSV upload, Excel upload (`xlsx`), paste-CSV, sample data, and a CSV
  template download.
- Auto column detection with a manual mapping fallback UI.
- Three chart views (combined / forecast-only / confidence bands) via
  Recharts, stat cards, and a short insights list.
- CSV export and PDF export (`jspdf` + `html2canvas`, unchanged libraries).

## Running it

```bash
pnpm install   # or npm install --legacy-peer-deps
pnpm dev       # http://localhost:3000
pnpm build
```

Verified with `tsc --noEmit` and `vite build` — both pass clean.

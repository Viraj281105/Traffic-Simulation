# UrbanFlow Frontend

The landing page and dashboard for UrbanFlow: a **React 19 + TypeScript** application built with **Vite**, rendering simulations on **HTML5 Canvas** and charts with **Recharts**. It presents what the backend measures — it never runs a simulation and never computes a metric.

**Owner:** Khushi Kashyap · **Architecture:** [docs/architecture/03-frontend-architecture.md](../docs/architecture/03-frontend-architecture.md) · **Product:** [docs/product/README.md](../docs/product/README.md)

---

## What it contains

| Area                | Where                                                                                                                         | What                                                                                      |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Landing page        | `index.html`, `src/landing/`                                                                                                  | "Signal or roundabout? Try both." — narrative, how it works, method                       |
| Guided comparison   | `src/components/guided/`                                                                                                      | Step 1 Your junction → Step 2 Watch both run → Step 3 Results, with the reliability check |
| Maps                | `IntersectionMap.tsx`, `RoundaboutMap.tsx`, `snapshotInterpolator.ts`                                                         | Canvas rendering of both junctions with interpolated motion                               |
| Specialist layer    | `ComparativeDashboard.tsx`, `MetricSections.tsx`, `analytics/`, `WeightedScoringPanel.tsx`                                    | Every metric, live charts, weighting, CSV                                                 |
| Saved               | `HistoryDashboard.tsx`, `RunPage.tsx`, `ComparePage.tsx`                                                                      | Saved runs, provenance, re-run, exports, compare up to six                                |
| Research Lab        | `ResearchHub.tsx`, `VolumeAnalysisDashboard.tsx`, `ValidationDashboard.tsx`, `JunctionStudyPage.tsx`, `ThreeWayStudyPage.tsx` | Traffic-level sweep, statistical validation, single-strategy views                        |
| Metric presentation | `src/metrics/catalog.ts`, `src/metrics/plainLanguage.ts`                                                                      | One description per metric; plain-language readings                                       |
| Backend access      | `src/services/`, `src/hooks/`                                                                                                 | REST, WebSocket (with backoff), live-session handshake, study jobs                        |

Routes: `/app/comparative` (default), `/app/history`, `/app/runs/<id>`, `/app/compare?runs=…`, `/app/research`, `/app/volume`, `/app/validation`, `/app/junction`, `/app/three-way`, `/app/signal`, `/app/roundabout` (`src/routing.ts`).

---

## Develop

```bash
npm install
npm run dev            # http://localhost:5173 (landing) and /app/comparative
```

The dev server proxies `/api` and `/ws` to the backend on `http://localhost:8000` (or `URBANFLOW_DEV_BACKEND` in the Docker dev stack). To point at another backend, set `VITE_API_URL` / `VITE_WS_URL` (see `.env.example`). In `npm run dev` you are signed in as "Local developer" — the backend must run with `DEV_AUTH_BYPASS=1` to accept it; set `VITE_DEV_AUTH_BYPASS=false` to exercise real Cognito sign-in. The bypass is compiled out of production builds.

## Quality

```bash
npm run test           # Vitest
npm run type-check     # tsc --noEmit
npm run lint           # ESLint
npm run format         # Prettier check (format:fix to apply)
npm run build          # tsc && vite build
```

What each test area protects: [docs/testing/README.md](../docs/testing/README.md).

## Production image

`Dockerfile` builds the bundle and serves it from `nginx-unprivileged` on port 8080 using `templates/default.conf.template` (SPA route fallback, `/api` · `/ws` · `/health` proxy, server-side API-key header, optional basic-auth gate). See [docs/deployment/README.md](../docs/deployment/README.md).

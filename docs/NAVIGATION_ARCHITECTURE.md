# UrbanFlow navigation architecture (audit and implementation)

Status: **IMPLEMENTED & VERIFIED** on `viraj-dev` (V5.4).

## 1. Current hierarchy

The dashboard is one document (`app.html`) with a lightweight client-side router
(`frontend/src/routing.ts`). Every view is rendered by the dashboard shell
in `App.tsx`, preserving session state and cleanly mounting/unmounting live streams.

| Section (`MainNav`) | Sub-navigation / Grouping | Routes |
| ------------------- | ------------------------- | ------ |
| **Simulate** | Step bar: Configure → Watch run → Results | `/app/comparative` |
| **Research lab** *(sign-in)* | **Overview**<br/>**Studies:** Custom junction study · Three-way study · Statistical validation · Traffic-level sweep<br/>**Single control:** Signal on its own · Roundabout on its own | `/app/research`<br/>`/app/junction`<br/>`/app/three-way`<br/>`/app/validation`<br/>`/app/volume`<br/>`/app/signal`<br/>`/app/roundabout` |
| **Experiments** *(sign-in)* | **Decision & Discovery:** Planner · Scenario planning · Experiment Copilot · Discovery Lab · Stress Lab<br/>**Trust & Networks (Phases 4–6):** Trust and reports (`/app/insights`) · Networks (`/app/network`) · Resilience (`/app/resilience`) | `/app/planner`<br/>`/app/scenarios`<br/>`/app/copilot`<br/>`/app/discovery`<br/>`/app/stress`<br/>`/app/insights`<br/>`/app/network`<br/>`/app/resilience`<br/>`+ /app/experiments/:id` |
| **Saved** | Saved runs, comparison viewer | `/app/history`, `/app/runs/:id`, `/app/compare?runs=` |
| **Developer** *(utility)* | Personal access tokens (PATs), API credentials | `/app/tokens` |
| **Admin** *(admins only)* | Platform admin panel | `/app/admin` |

Section definitions and metadata live in `frontend/src/components/shell/sections.ts` (`SECTIONS`) and are rendered by `frontend/src/components/shell/Navigation.tsx`.

## 2. Problems resolved during V3–V5 evolution

1. **API tokens promoted to top-level utility:** Tokens moved out of nested experiment sub-menus to a 1-click **Developer** tab in the utility bar.
2. **Clear naming hierarchy:** Disambiguated "Your junction" (the wizard step) from "Custom junction study" (batch research tool).
3. **Structured Research Lab:** Replaced flat 8-tab menu with clean grouped navigation (Overview, Multi-Alternative Studies, Single Control live inspection).
4. **Unified Experimentation Suite:** Placed scenario planning alongside Planner, Copilot, Discovery Lab, Stress Lab, and newly introduced Phase 5/6 suites (Trust & Insights, Networks, Resilience).
5. **Seamless Deep-Linking & Route Fallbacks:** All 18 routed views are mirrored across the Vite dev server, Vite preview, and Nginx SPA template (`frontend/templates/default.conf.template`), backed by `routing.test.tsx`.
6. **Cross-Study Discovery:** Research and Experiment pages conclude with a "related tools" strip for intuitive cross-study navigation without returning to root hubs.

## 3. Current active hierarchy

```
Header (persistent on every view)
├─ Primary workflows (segmented tabs)
│  ├─ Simulate          /app/comparative           step bar: Configure → Watch both run → Results
│  ├─ Research lab      /app/research              (sign-in)
│  │    Overview
│  │    Studies:        Custom junction study · Three-way study · Statistical validation · Traffic-level sweep
│  │    Single control: Signal on its own · Roundabout on its own
│  │    Single control: Signal on its own · Roundabout on its own
│  ├─ Experiments       /app/planner               (sign-in)
│  │    Planner · Scenario planning · Experiment Copilot · Discovery Lab · Stress Lab
│  │    Trust and reports (/app/insights) · Networks (/app/network) · Resilience (/app/resilience)
│  │    (+ current experiment trailing crumb on /app/experiments/:id)
│  └─ Saved             /app/history               (+ run and compare pages)
└─ Utilities (right side)
   ├─ Developer         /app/tokens  (one click from anywhere; sign-in)
   ├─ Admin             /app/admin   (admins only)
   └─ Theme toggle, account session
```

## 4. User Journeys

| Journey | Mechanism | Delivery |
| ------- | --------- | -------- |
| First visit | Lands on Simulate tab (`/app/comparative`), step "Configure" | Immediate zero-auth 2D preview |
| Run → save → find again | Results → Save → toast with **Open saved run** link | Opens `/app/runs/:id` |
| Results → deeper analysis | "Take it further" links on the results page | Direct deep-link to Planner or Research Lab |
| Network inspection | Experiments → Networks (`/app/network?tab=map\|congestion\|metrics\|calibration\|rl\|twin\|loadtest`) | Interactive MapLibre & SVG view |
| Incident & Resilience | Experiments → Resilience (`/app/resilience?tab=incidents\|strategies\|priority\|v2x\|account\|jobs`) | Incident injection & priority audit |
| Manage API tokens | Developer tab in the header (1 click from anywhere) | `/app/tokens` with PAT generation |

## 5. Architectural Invariants

- **Routing / deep links:** All paths defined in `VIEW_ROUTES` (`frontend/src/routing.ts`). Query parameters (`?tab=`, `?signin=1`) preserve sub-tab state on refresh.
- **Teardown on unmount:** Simulation WebSockets are cleanly closed when navigating away from Simulate/Single control views to prevent ghost CPU load on the backend.
- **Authentication gating:** Sensitive tools (`requiresAuth: true`) prompt Cognito / Dev-bypass sign-in before mounting.

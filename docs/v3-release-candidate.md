# UrbanFlow V3.0 — release candidate notes, claims register and runbook

Branch `viraj-dev`. This page is the W9 summary: what V3.0 contains, what may and may not be claimed about it,
how to run and check it, and what is still open. Detailed pages are linked from each row.

## Contents

| Area | What exists | Detail |
| --- | --- | --- |
| Robustness Lab (W1) | Uncertainty experiments, paired comparisons, eligibility classes, full results viewer (limitations first, comparisons, regret and preference share, stability and variance split, assumptions, provenance) | [uncertainty.md](research/uncertainty.md) |
| Signalised roundabouts (W2), strategy registry (W3), driver aggression (W4) | As in the W1–W4 records | [ROADMAP.md](ROADMAP.md) |
| Experiment Copilot (W5) | Question → validated proposal → confirm → experiment; grounded interpretation | [ai/copilot.md](ai/copilot.md) |
| Dashboard AI assistant (merged from `main`) | Summary, chat and config patch with deterministic fallback, daily caps and kill switch | [ai/copilot.md](ai/copilot.md) (cost controls) |
| Discovery Lab (W6) | Bounded evolutionary search with held-out evaluation against unchanged baselines | [research/discovery-lab.md](research/discovery-lab.md) |
| Platform (W7) | Personal access tokens and scopes (Plan → API tokens), quotas, cancel/resume, `.ufpkg` packages, Python SDK | [operations.md](operations.md), [sdk/python/README.md](../sdk/python/README.md) |
| Stress Lab and breakpoints (W8) | Reproducible stationary-extreme scenarios, failure classes, breakpoint explorer | [research/stress-testing.md](research/stress-testing.md) |
| API reference | 34 `/api/v3` operations with scopes | [v3-api-reference.md](v3-api-reference.md) |

## Claims register

| Allowed | Not allowed |
| --- | --- |
| "Robustness under the stated, assumed uncertainty, in this simulator" | Any real-world performance or safety claim ("Real-world validity: none — assumptions only") |
| "Eligible / indicative / exploratory" exactly as the eligibility check reports it | Calling a result robust when the class is not `eligible` |
| "Rule-based experiment assistant"; "AI-assisted proposal — validated by the backend and confirmed by you" (only when a model produced it) | "AI Copilot" as an AI feature: no provider has passed `copilot-eval-v1`, so `aiCopilot` is false |
| "Model-generated interpretation of the measured results shown" (only text that passed grounding) | "AI-verified", "AI-optimised", or that the model ran or measured anything |
| "Bounded multi-objective evolutionary search"; "found by search under these conditions"; EXPERIMENTAL | "Learned", "AI-discovered best/optimal/recommended" strategy |
| "Integrity is not authenticity": a verified package is internally consistent | That a package proves who produced it |
| "Replay class from recorded provenance" | That verification re-ran the experiment |
| "Stationary extremes" stress scenarios | Surges, incidents, lane closures (not modelled) |
| Safety proxies (near misses, collisions in the model) | Predictions of real crashes |

## Runbook

1. **Configure** `backend/.env` / the EC2 `.env`: `API_KEY`, Cognito variables, `CORS_ORIGINS`, `ADMIN_EMAILS`;
   optional `GROQ_API_KEY` (AI model), `AI_COPILOT_ENABLED`, `AI_CALLS_PER_*`, `COPILOT_*_PER_DAY`. No secret
   is needed in GitHub beyond the existing EC2 SSH secrets.
2. **Network:** Compose pins the nginx container to `172.30.77.10` on `172.30.77.0/24` and the backend trusts only
   that address (`TRUSTED_PROXY_IPS`). Change `URBANFLOW_SUBNET` / `URBANFLOW_FRONTEND_IP` together if the range
   collides; behind another load balancer configure nginx's real-IP module. After deploying, check that two
   visitors are counted separately.
3. **Deploy:** merge into `deployment`; the workflow rebuilds on EC2 and health-checks. Database changes are
   additive and automatic (`uf_pats`, `uf_audit_log`, `uf_usage`, two new `uf_experiments` columns).
4. **Check:** `GET /health`, `GET /api/v3/capabilities` (features and quotas), sign in, create a token, run the
   SDK smoke: `python -m urbanflow_client capabilities`.
5. **Switch the AI off** at any time: `AI_COPILOT_ENABLED=0` (everything falls back to rule-based answers).

## Quality gates run for this candidate

* Backend: ruff, ruff format, mypy (strict) clean; architecture rules (SQL only in stores) pass; the
  non-slow suite with the coverage gate (result recorded in the commit message of the W9 commit).
* Frontend: ESLint, Prettier, TypeScript, 504 unit tests, production build — all pass.
* SDK: ruff, mypy `--strict`, 34 unit tests, integration tests against the real app and the OpenAPI snapshot.
* Schema validation and the OpenAPI snapshot contract test.
* Dependency audit: production npm dependencies report 0 vulnerabilities after `npm audit fix`; repository
  scan found no committed secrets.

## Still open

* **D-AI1 / C3:** a model provider evaluation on `copilot-eval-v1` (and an independently written eval set).
* **D9, D10:** Discovery Lab runs on three declared regimes and the runtime benchmark on the presentation
  machine (one development-machine measurement: 52 runs of 90 simulated seconds in 60 s on 8 workers).
* **Slow simulation suite** (`pytest -m slow`) runs in its own CI job; not re-run locally for this candidate.
* **Dev-only tooling:** `vitest` / `tinypool` advisories need a major upgrade of the test runner (not shipped).
* **375 px views:** the new pages use responsive grids and scrolling tables; a device check is still to do.
* **Process-local counters** (rate limits, AI budget) assume one backend process; jobs and Discovery/Stress
  results are kept in memory (packages are the durable record for searches).

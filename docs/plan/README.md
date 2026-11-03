# UrbanFlow plan: V3.1 – V6.1 (W31 – W60)

The delivery plan that follows V3.0. Thirty weeks, four phases, twenty features, two people.

| Page | What it holds |
| --- | --- |
| This page | Principles, calendar, ownership, gates, demo protocol, risks, decisions, how the plan is tracked |
| [WEEKLY_PLAN.md](WEEKLY_PLAN.md) | Week by week: dates, version, sprint goal, Viraj's work, Khushi's work, status |
| [FEATURE_SPECIFICATIONS.md](FEATURE_SPECIFICATIONS.md) | Scope, deliverables and acceptance checks for each of the 20 features |

## 1. Goals

1. Ship a substantial release roughly every two months, never a gimmick: each release has a headline capability, an exit gate and a demo.
2. Move beyond a single junction toward real networks and real data.
3. Make quality provable: statistics with intervals, reproducible runs, property-based tests and AI evals that fail the build.
4. Broaden the stack deliberately: Go, AWS, Kubernetes, Airflow, event streaming, MLOps, observability.
5. Keep every claim honest. The V3.0 claims register stays in force, and every new capability states what it does and does not show.

## 2. Users

| User | What they do with UrbanFlow | Priority |
| --- | --- | --- |
| Traffic engineer (city or consultancy) | Tests signal and junction changes before they are built | Primary |
| Urban planner | Asks what-if questions: a new school, a new development, an event day | Secondary |
| Researcher / student | Benchmarks controllers (fixed-time, adaptive, learned) reproducibly | Secondary |
| Decision-maker | Reads a short, honest report and approves or rejects | Consumer |

UrbanFlow is **advisory only**. It recommends; it never controls live signals.

## 3. Calendar

Weeks run Monday to Friday. The plan continues the project week numbering (this plan is W31 – W60). The version goes up by 0.1 each week, rolling over at .9.

| Phase | Weeks | Dates | Versions | Theme | Features |
| --- | --- | --- | --- | --- | --- |
| 4 | W31 – W38 | 2 Nov – 25 Dec 2026 | V3.1 – V3.8 | Trustworthy Results | F4, F6, F7, F8, F9, F3, F1 |
| 5 | W39 – W46 | 28 Dec 2026 – 19 Feb 2027 | V3.9 – V4.6 | Beyond One Junction | F5, F11, F15, F18 |
| 6 | W47 – W54 | 22 Feb – 16 Apr 2027 | V4.7 – V5.4 | Resilience and Cloud | F13, F12, F2, F16, F14 |
| 7 | W55 – W60 | 19 Apr – 28 May 2027 | V5.5 – V6.0 | Cooperation and Governance | F19, F20, F17, F10 |
| Showcase | – | 31 May – 2 Jun 2027 | V6.1 | Final demo and buffer | all |

Some features span phases: F18 starts in Phase 4 on a single junction and finishes on the network in Phase 5; F14 starts in Phase 5 and finishes in Phase 6; F19 starts in Phase 6 and finishes with the hardware demo in Phase 7.

The V3.0 final showcase (Thursday 7 January 2027) falls in W40 and is a fixed commitment; capacity that week is reduced.

## 4. How the work is split

| Person | Owns |
| --- | --- |
| **Viraj** | Simulation core, data, backend, infrastructure, platform, and the complex simulation-facing UI: multi-junction map viewer, congestion heatmap, network-level metric views, canvas markers |
| **Khushi** | ML and reinforcement learning (F18: environment, training, MLflow, registry, evaluation), frontend, analytics, dashboards, reports, demo scripts |

The last week of each phase is a **release week**: hardening, documentation, ADRs, reproducibility audit, demo build tag. Nothing new starts in release week.

## 5. Demo Mondays

The last Monday of every month is reserved **only** for testing the system and preparing the demo. No feature work.

| Demo | Date | Week | What it shows |
| --- | --- | --- | --- |
| D1 | Mon 30 Nov 2026 | W35 | Confidence intervals, tests and CI, run store, local Kubernetes |
| D2 | Mon 28 Dec 2026 | W39 | The Phase 4 release |
| D3 | Mon 25 Jan 2027 | W43 | Corridor and grid, OSM import, calibration, RL policies |
| D4 | Mon 22 Feb 2027 | W47 | The Phase 5 release |
| D5 | Mon 29 Mar 2027 | W52 | Incidents and weather, emergency priority, AWS deployment, V2X |
| D6 | Mon 26 Apr 2027 | W56 | The Phase 6 release |
| D7 | Mon 31 May 2027 | – | Final demo |

Protocol:

1. End of the previous Friday: tag a demo build (`demo-YYYY-MM`) and stop merging.
2. Monday morning: deploy the tag to a clean environment and run the full smoke test.
3. Monday midday: write the demo script around what actually works. Record failures in a list instead of fixing them, except blockers.
4. Monday afternoon: rehearse end to end and record a backup video.
5. Tuesday: back to the plan.

Weeks containing a demo Monday have four working days.

## 6. Gates

| Gate | Week | Passes when |
| --- | --- | --- |
| G-REL1 | W38 | Intervals and p-values reported; re-run from a manifest is identical; eval and coverage gates enforced; deploys to Kubernetes through CI |
| G-CAL | W41 | Simulated flows match real counts within an agreed error, reported openly |
| G-REL2 | W46 | A real network of 10+ junctions runs end to end; calibration error reported; RL compared with baselines on the network; dashboards and SLOs live |
| G-REL3 | W54 | Resilience scores for every strategy; emergency pre-emption cuts response time; platform on AWS via Terraform and multi-tenant; twin on live-style feeds |
| G-AIM | W57 | The signal-free intersection manager passes safety validation |
| G-REL4 | W60 | Connected vehicles measured on hardware; platoon throughput effect shown; signal-free vs signals compared; approvals with audit trail; cost visible per run |

A gate that does not pass moves scope inside its release. The release date does not move.

## 7. Working rules

- **Scope cuts, not date cuts.** If a phase runs behind, scope moves inside it; release weeks and demo Mondays are fixed.
- **Tests are the safety net.** From W31 every push runs the suite; AI evals and property tests gate merges. Nothing is skipped to hit a date.
- **ADR first** for any structural decision (network model, event stream, auth changes, cost control).
- **Claims discipline.** `docs/v3-release-candidate.md` holds the claims register. New features add rows; results are never described beyond what they show.
- **Conventions.** Work happens on `viraj-dev`; each person owns separate directories to avoid collisions.

## 8. Risks

| Risk | Affects | Mitigation |
| --- | --- | --- |
| Review time is the real limit, not coding speed | All | Short ADRs, automated gates, slack weeks (W45, W53, W59) |
| Khushi's RL work (W34 – W44) depends on the engine and platform, which Viraj owns | F18 | Engine interface frozen with F5's ADR in W39; Viraj keeps Airflow, cluster and run store; check at each phase start whether the split still balances |
| Open traffic data hard to find | F11, F14 | Choose the city and datasets before W39 |
| No live traffic feed source | F14 | Decide by W46; replay mode remains the fallback inside the same feature |
| AWS account or budget not approved | F2, F17, F7 | Confirm owner and cap by W35; use local stand-ins until then |
| Hardware lead time | F19 | Order by W46 |
| Largest algorithms (network engine, signal-free intersections) overrun | F5, F20 | Slack weeks directly after each |
| Exams and leave not yet in the calendar | All | Add them and re-plan slack |

## 9. Decisions needed

1. AWS account, owner and monthly budget cap (by W35).
2. Calibration city and open datasets (before W39).
3. Live traffic feed source for the twin (by W46).
4. Hardware purchase for the signal-head demo (by W46).
5. Exam and leave weeks for both people.

## 10. How the plan is tracked on GitHub

- **Milestones:** one per phase (`Phase 4: Trustworthy Results (V3.1–V3.8)` … `Phase 7: …`) plus `Final showcase (V6.1)`.
- **Weekly issues:** one issue per week (`[V3.1 W31] …`) containing the goal, the gate if any, and two task lists, one for each person.
- **Feature epics:** one issue per feature (`[F6] …`, label `tracking`) holding the scope and acceptance checks and linking the weekly issues where it is worked.
- **Labels:** `phase-4` … `phase-7`, `owner-viraj`, `owner-khushi`, `demo-monday`, `release-week`, `gate`, plus the existing `tracking`, `research`, `platform`, `simulation`, `frontend`, `backend`.
- **Status:** a weekly issue closes when both task lists are complete; a feature epic closes when every acceptance item is ticked with evidence recorded.

## 11. Where this came from

The plan merges three sources: the Director's brief (Go, AWS, cloud/DevOps, Kubernetes, Airflow, AI evals, harder pytest, beyond a single junction), the Confluence future-scope list (emergency vehicles, RL control, connected vehicles, platooning, autonomous intersections, uncertainty, weather, incidents, large networks, digital twin) and additions made during planning (reproducibility and lakehouse, decision reports, metrics, governance, real-data interoperability, observability, multi-tenancy, cost control). Overlapping ideas were merged: for example the Confluence digital twin and the event-streaming idea became F14, and platooning with autonomous intersection management became F20.

Earlier planning material (V1.0 – V3.0 roadmaps, audits, ADRs) remains in `docs/roadmap/`, `docs/ROADMAP.md` and `docs/decisions/` as the record of what was built.

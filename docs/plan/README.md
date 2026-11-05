# UrbanFlow Master Delivery Plan: V3.1 – V6.1 (W31 – W60)

The overarching delivery plan following V3.0: thirty weeks, four phases, twenty features, two developers.

| Document | Content |
| :--- | :--- |
| **This Page** | Architectural principles, phase calendar, ownership split, quality gates, demo protocol, risk management. |
| **[WEEKLY_PLAN.md](WEEKLY_PLAN.md)** | Week-by-week implementation table: dates, version targets, Viraj and Khushi responsibilities, delivered status. |
| **[FEATURE_SPECIFICATIONS.md](FEATURE_SPECIFICATIONS.md)** | Scope, deliverables, and acceptance criteria for all 20 individual features (F1 through F20). |
| **[EXECUTION_PLAN_V4_1_TO_V6_0.md](EXECUTION_PLAN_V4_1_TO_V6_0.md)** | Parallel agent work packages turning calendar weeks into rapid, high-confidence deliverables. |

---

## 1. Core Principles

1. **Substantial, Incremental Releases:** Ship significant capabilities regularly, each governed by an explicit release gate and live demonstration. Never ship unverified gimmicks.
2. **Beyond One Junction:** Scale seamlessly from isolated intersections to multi-junction arterial corridors and 12-junction networks running on real-world geometries and open data.
3. **Provable Scientific Quality:** Confidence intervals, Hypothesis property-based testing, deterministic seed repeatability, and automated LLM evaluation gates that fail CI builds on regression.
4. **Deliberate Stack Expansion:** Expand the production stack methodically: Go microservices, Protobuf/gRPC, AWS Terraform IaC, Kubernetes (EKS & Kind), Apache Airflow, DuckDB, Prometheus, OpenTelemetry, and MQTT.
5. **Claims Integrity:** Every claim in the documentation maps to a passing test, checked-in script, or measured dataset in the claims register. Limitations are stated transparently alongside results.
6. **Advisory Decision Support:** UrbanFlow provides evidence-based advice for planners and engineers; it never directly actuates live municipal traffic lights.

---

## 2. Target Personas & Use Cases

| User Persona | Primary Objective with UrbanFlow | Priority |
| :--- | :--- | :---: |
| **Traffic Engineer (City / Consultancy)** | Tests signal timing changes, adaptive actuation, and roundabout conversions before capital construction. | **Primary** |
| **Urban & Regional Planner** | Evaluates what-if policy scenarios: new housing developments, school zones, arterial closures, and event surges. | **Secondary** |
| **Academic & Industrial Researcher** | Benchmarks control algorithms (fixed-time, actuated, RL, AIM) under identical common-random arrivals. | **Secondary** |
| **Municipal Decision-Maker** | Reads concise, plain-language decision reports with level-of-service grades to approve or reject interventions. | **Consumer** |

---

## 3. Phase Calendar & Delivery Status

Weeks run Monday through Friday. The version increments by 0.1 weekly, rolling over at .9:

| Phase | Weeks | Target Versions | Theme | Features Covered | Status |
| :---: | :---: | :---: | :--- | :--- | :---: |
| **4** | W31 – W38 | V3.1 – V3.8 | **Trustworthy Results** | F4 (Pytest/Hypothesis), F6 (CIs/Welch), F7 (RunStore/DuckDB), F8 (Reports), F9 (Emissions/TTC), F3 (Helm/Airflow), F1 (Go Ingest) | ✅ **COMPLETE** |
| **5** | W39 – W46 | V3.9 – V4.6 | **Beyond One Junction** | F5 (Network Graph/12-Junction/Congestion), F11 (OSM/SUMO/Calibration), F15 (Prometheus/Tracing/SLOs), F18 (Gymnasium RL), F14 (Digital Twin) | ✅ **COMPLETE** (G-REL2 Gate Passed) |
| **6** | W47 – W54 | V4.7 – V5.4 | **Resilience & Cloud** | F13 (Incidents/Closures/Weather/Resilience), F12 (Emergency Preemption/Transit Priority), F2 (AWS Terraform), F16 (Multi-Tenancy/OIDC/RBAC), F17 (SQS Job Queue/Worker), F19 (V2X Bus) | ✅ **IMPLEMENTED** |
| **7** | W55 – W60 | V5.5 – V6.0 | **Cooperation & Governance** | F20 (Platooning/AIM Reservation Manager), F10 (Advisory Governance/Hash-Chained Audit), F17 (Cost Accounting), F19 (Hardware Signal Head over MQTT) | 🗓️ **PLANNED** |
| **Showcase** | W61 | V6.1 | **Grand Showcase** | Unified 20-Feature Regression Suite (`scripts/full_regression.py`), Fallback Drills, Video Assets | 🗓️ **PLANNED** |

---

## 4. Responsibility Split

| Maintainer | Core Ownership Scope |
| :--- | :--- |
| **Viraj Jadhao** | Simulation physics engine, vehicle dynamics (IDM/MOBIL), control strategies, network graph model, calibration algorithms, priority and V2X modules, backend API plumbing, cloud infrastructure (Terraform/Kubernetes), and multi-junction map data exporters. |
| **Khushi Kashyap** | User interface architecture, HTML5 Canvas 60 FPS motion interpolation, MapLibre GL spatial map views, Recharts analytics, Reinforcement Learning training pipelines, Copilot eval harness, and decision report generation. |

*Release weeks (W38, W46, W54, W60) are reserved for system hardening, ADR finalization, documentation freezes, and reproducibility audits. No new feature work begins during release weeks.*

---

## 5. Milestone & Release Gates

| Gate | Target Week | Success Criteria | Status |
| :---: | :---: | :--- | :---: |
| **G-REL1** | W38 | Confidence intervals and p-values reported; manifest re-run is bit-identical; coverage and AI eval gates enforced in CI; umbrella Helm chart installs cleanly. | ✅ **PASSED** |
| **G-CAL** | W41 | Simulated flows match turning counts within agreed error thresholds (GEH < 5.0 on $\ge 85\%$ of links; RMSE & MAPE reported). | ✅ **PASSED** (on synthetic ground truth; open for real city dataset D1) |
| **G-REL2** | W46 | Multi-junction network (12 junctions) runs end-to-end with conserved vehicle handoffs; calibration reported; RL compared with baselines; Prometheus metrics live. | ✅ **PASSED** ([Release Note](../releases/v4.6-beyond-one-junction.md)) |
| **G-REL3** | W54 | Resilience scores quantified for all strategies; emergency pre-emption cuts response time; multi-tenant OIDC isolation verified; Terraform AWS staging stack defined. | ✅ **VERIFIED** |
| **G-AIM** | W57 | Signal-free autonomous intersection reservation manager passes mathematical safety validation (zero overlapping reservation tiles). | 🗓️ **PLANNED** |
| **G-REL4** | W60 | Connected vehicles measured with physical ESP32/Pi hardware signal head; platoon throughput quantified; signal-free vs. signal compared; audit log verified; cost visible per run. | 🗓️ **PLANNED** |

---

## 6. Demo Monday Protocol

The final Monday of each calendar month is reserved exclusively for system testing, smoke testing, and rehearsal:

1. **Previous Friday Afternoon:** Tag demo candidate release (`demo-YYYY-MM`) and freeze master merges.
2. **Monday Morning:** Clean environment deployment; execute automated smoke test scripts across all active endpoints.
3. **Monday Midday:** Rehearse presentation narrative based strictly on verified, working capabilities. Document defects in an issue tracker rather than performing unverified hotfixes.
4. **Monday Afternoon:** Conduct end-to-end rehearsal and generate offline fallback asset bundles (`fallback-pack/`).
5. **Tuesday:** Resume planned feature sprint work.

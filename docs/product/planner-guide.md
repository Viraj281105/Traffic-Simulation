# Planner guide — running a junction study

> **Status:** Current · V2.0 · the planner page is `/app/planner` (the **Plan** tab). It is a browser workflow over the [`/api/v2/planning` API](../api/README.md#10-decision-support-api--apiv2-v18v20). Sign-in is required.

The planner compares control alternatives for **one junction** on the same simulated traffic and shows the evidence: differences from a baseline, their uncertainty, and what could not be measured. **It reports evidence, not a verdict:** it never ranks alternatives or recommends one.

## 1. Build the scenario

Start from a preset or build the junction yourself (lanes, lane arrows, demand per road, turning shares, vehicle mix, duration). The builder checks the scenario with the server as you edit and explains any problem in plain language.

## 2. Choose alternatives and repetitions

| Setting | Meaning | Server limit |
| --- | --- | --- |
| Alternatives | Each is a control (fixed-time signal, adaptive signal, roundabout) with an optional label. **The first row is the baseline**; *Make baseline* moves a row to the top | 2–6 in the planner (the API accepts 1–6) |
| Seeds | Repetitions per alternative. Every alternative uses the **same seeds**, so differences are paired | 1–30 |
| Demand levels | Multiples of the scenario's demand (×0.5 … ×2) | 1–5 |

## 3. Check the cost and run

Before running, the page shows the number of simulations the study needs (alternatives × demand levels × seeds; at most 240). **No run-time estimate is shown**: none has been measured for the server, and time depends on the machine, the scenario duration and how congested the junction is.

*Run study* starts a background job. The page moves to `/app/planner?study=<id>` and shows how many simulations have finished. You can leave the page; the link re-opens the study. If the server is already running two planning studies, it says so — wait for one to finish and start again. A study that fails shows the server's reason.

## 4. Read the evidence

| Part | What it tells you |
| --- | --- |
| Validity banner | Whether observed traffic data were attached (studies started from the planner never are: **not field-calibrated**), that results are exploratory and do not transfer to other junctions, and the vehicle-limit warning if it applies |
| Indicators table | Per alternative and demand level: mean across seeds and its confidence interval. **"not available" means the value could not be measured — it is never shown as 0** |
| Paired difference table | Alternative minus baseline on the same seeds, with its interval and a reading: *better/worse than the baseline*, *tie — within the tie tolerance*, *inconclusive — the seeds could not separate them*, or *not available* |
| Not available in this study | Indicators this build cannot report (for example minimum time-to-collision), with the reason |
| Findings | Plain-language statements, each with the evidence paths in the result it rests on, a confidence level and caveats |
| Reliability and limitations | Sample adequacy (e.g. fewer than 5 seeds is "indicative only"), high-variability warnings, and what the study cannot claim |

## 5. Report and reproduce

* **Download JSON / Markdown / CSV** — the server's own report files.
* **Reproducibility** shows the study id, the scenario, input and result fingerprints, the source commit and the seeds. **Reproduce** re-runs the stored request and reports whether the result fingerprint is identical. "Not reproduced" also says when the server now runs a different commit.

## 6. Re-open, privacy and deletion

* Re-open a finished study from its link or with *Re-open a study by id*; finished studies survive a server restart. A study that was still running when the server stopped is lost.
* Studies are private: another user's study id answers "not found".
* A finished or failed study can be deleted through the API (`DELETE /api/v2/planning/{id}`); the planner page has no delete button yet.

## What the planner does not do (V2.0)

Attaching observed traffic data (the calibration API exists but has no planner step), network or multi-junction studies, cancelling a running study, and fitting model parameters. These are recorded as accepted-gap candidates in the [V2.0 completion audit](../roadmap/V2_COMPLETION_AUDIT.md) §7.8.

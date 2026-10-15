# Robustness Lab demo: a precomputed result

This folder is the **fallback** for the V3.0 Robustness Lab demonstration: a result that was computed once, saved with checksums, and can be shown with no backend and no simulation.

```bash
python scripts/v3_demo.py --offline docs/research/examples/robustness-demo
```

The command verifies `SHA256SUMS` first and refuses to print a file that was changed after it was saved. It always says that the result is precomputed and not a live run.

| File | What it is |
| --- | --- |
| `experiment.json` | the request that was submitted (`urbanflow-experiment` v1) |
| `result.json` | the result the server returned (`urbanflow-experiment-result` v1) |
| `MANIFEST.json` | commit, Python version, platform, wall time, and whether a second run reproduced the fingerprint |
| `SHA256SUMS` | checksums of the three files above |

**Where it came from.** Generated on 2026-10-15 by `python scripts/v3_demo.py http://localhost:8001 --verify --save …` against a backend running commit `ca09d3d`, on Windows with Python 3.14.7 and 8 worker processes. The experiment ran in 203.65 s. Running it a second time gave the **identical result fingerprint** (`52b7b3d275d0e8ca`), through the real process pool. That is exact replay on this machine and commit only; on another revision, Python or machine, expect comparable results, not identical ones (see [uncertainty §9](../../uncertainty.md#9-reproducibility)). The live run is repeatable with the same command and no `--save`.

## The study

A single junction (four one-lane arms, 600 vehicles per hour on each, a mixed vehicle population) is compared under three kinds of control: a **fixed-time signal** (the baseline), an **adaptive signal** and a **conventional roundabout**. In each of **24 sampled conditions** four inputs vary over ranges the author *assumed*:

| Factor | Range | Reason given |
| --- | --- | --- |
| Demand | ×0.7 to ×1.3 | peak-hour flow varies by about 30 % between days |
| Turning shares (straight ↔ turning) | −0.3 to +0.3, most likely 0 | shares drift with local events |
| Vehicle mix (light ↔ heavy) | −0.4 to +0.4 | buses and trucks vary between weekdays |
| Driver headway | ×0.8 to ×1.3, most likely 1 | driver behaviour is uncertain; a proxy, not a measured reaction time |

24 conditions × 3 alternatives × 2 replications = **144 runs**; every alternative sees the same traffic and the same random numbers in each condition. The measure is mean delay in seconds (lower is better), over the 105 s after a 15 s warm-up.

## What the result says (and does not)

| Against the fixed-time signal | Better | About the same | Worse | Mean difference (95 % interval) |
| --- | :-: | :-: | :-: | --- |
| Adaptive signal | 54 % (13 of 24) | 8 % | 38 % (9 of 24) | −0.74 s (−2.58 to 1.17) |
| Conventional roundabout | 8 % (2 of 24) | 21 % | 71 % (17 of 24) | +3.64 s (2.10 to 5.29) |

* **Roundabout.** In this simulation, under these assumptions, the conventional roundabout had more delay than the fixed-time signal in most conditions, by about 3.6 s on average, and the interval for the average difference stays above zero.
* **Adaptive signal.** The intervals include no difference at all: better in 13 conditions, worse in 9, and a mean difference that could be either sign. The experiment **cannot separate** the adaptive signal from the fixed-time one. That is a finding, not a failure.
* **Eligibility: exploratory only.** There are 24 valid conditions, fewer than the 30 needed for even an "indicative" label, and the precision criterion is not met (the 95 % Wilson half-width is 0.185; the limit is 0.10). Split-half stability is not computed yet. So **no robustness statement is made**: these proportions are a guide to what a larger run would examine, not a verdict.
* **Nothing about a real junction follows.** *Real-world validity: none — assumptions only.* Every range above is an assumption and the simulator is not calibrated to observed traffic. The demo shows the method working, not an answer about any road.

This is deliberately an honest, modest result: a run with more conditions (about 97 are needed for a ±10-point precision in the worst case) is what would let the adaptive-versus-fixed question be answered.

## Regenerating

```bash
cd backend && DEV_AUTH_BYPASS=1 python -m uvicorn src.main:app --port 8000
python scripts/v3_demo.py http://localhost:8000 --verify --save docs/research/examples/robustness-demo
```

A regenerated pack will differ in `generatedAt`, the commit and the timings; the result fingerprint changes only if the code, the experiment or the environment did. The method is explained in [Robustness under uncertainty](../../uncertainty.md); the API in the [`/api/v3` reference](../../../api/README.md#11-robustness-lab-api--apiv3-v30-in-development).

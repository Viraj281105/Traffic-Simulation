# V3.0 evaluation packages (E1–E4)

Recorded on the development machine on 2026-10-27 with the release-candidate code (8 workers). Each `.ufpkg`
verifies as internally consistent with replay class `exact` on that machine; `summary.json` holds the
fingerprints, run counts, wall times and headline numbers. All four are **exploratory** in size (12
conditions × 2 replications, or a small search): they demonstrate the workflow end to end, not a finding.

| Package | What it is | Headline (mean delay, s, lower is better) |
| --- | --- | --- |
| `E1-robustness.ufpkg` | Robustness experiment: fixed-time, adaptive, roundabout; demand ±20 % assumed | adaptive 17.8, fixed 21.2, roundabout 24.4 |
| `E2-signalised-roundabout-high-aggression.ufpkg` | The same junction under high aggression, plus the metered-entry roundabout | fixed 17.4, adaptive 19.9, roundabout 23.4, metered 27.3 |
| `E3-copilot-proposed.ufpkg` | The brief's question through the rule-based Copilot (quick study, uneven peak, high aggression) | adaptive 46.1, roundabout 52.2, signalised roundabout 60.4 |
| `E4-discovery-search.ufpkg` | Discovery search (uneven peak, high aggression, 114 runs) | Both shortlisted candidates do worse than the fixed-time and adaptive baselines on held-out seeds (reported, flag `bestOnTuningLosesOnHeldOut`) |

Verify any of them: `python -m urbanflow_client verify E1-robustness.ufpkg`, or upload through
`POST /api/v3/packages/verify`. Real-world validity: none — assumptions only.

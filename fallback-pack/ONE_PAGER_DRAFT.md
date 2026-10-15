# UrbanFlow V2.0 — evidence-based planning for signal and roundabout choices (one-pager, DRAFT)

**What it is.** A browser tool that simulates a junction under fixed-time signals, adaptive signals and a roundabout, compares them on the *same* traffic and random seeds, and reports evidence with its limits. It does not rank options or recommend a winner.

**What V2.0 delivers.** Build a scenario → compare alternatives with confidence intervals → read findings and their confidence → export a report (JSON, Markdown, CSV) → reproduce the study from its fingerprints. Per-user data is private. Release gate G-V2 passed 2026-10-13.

**Example (precomputed, 3 seeds per option, one-lane junction, 300 vehicles/h per arm).** At normal demand the adaptive signal served about 6 more vehicles than fixed-time (95 % CI 1.2 to 11.5), while the mean-delay difference was *inconclusive* — three seeds could not separate the options. This is what the tool is for: it shows when the evidence is not yet enough.

**Limits we state up front.**
- Results describe this simulated scenario only; **no field calibration** has been run and no real-world superiority is claimed.
- Safety and fuel/CO₂ indicators are exploratory proxies, not validated predictions.
- Few seeds give wide intervals; more seeds narrow them.

**Next (V3.0, design stage — nothing built yet).** Robustness analysis under uncertain demand and driver behaviour, signalised roundabouts, composable control strategies, a high-aggression driver profile, and two AI-assisted features — each gated on its own evidence.

*Draft: figures come from the rehearsal pack built on commit 886742f; regenerate on the frozen preview commit before printing.*

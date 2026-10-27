# Control Strategy Discovery Lab (V3.0 W6)

**Method:** bounded multi-objective evolutionary search (NSGA-II-style non-dominated sorting with crowding
distance) over the parameters of the registered control strategies, for one declared traffic regime. It
is a black-box optimiser, **not a learned model**, and it runs in pure Python on the existing process pool
(`backend/src/discovery/`). Every candidate is **EXPERIMENTAL**: found by search under the declared
regime and assumptions, in this simulator only; it says nothing about real-world performance or safety
and is never described as best, optimal or recommended.

## Search space (`space.py`)

Strategies: fixed-time signal, adaptive signal, conventional roundabout, signalised (metered-entry)
roundabout. Parameters and bounds: north–south and east–west greens 10–60 s with yellow 3–5 s and all-red
1–3 s (cycle kept within 40–120 s); adaptive minimum green 5–20 s, maximum green 25–90 s (at least 5 s
above the minimum), extension step 1–5 s; metering greens 10–40 s per phase pair, optional spillback guard
(threshold 1–6 stopped vehicles, hold 0–20 s); 1–2 circulating lanes. Genomes are repaired **only** by
clamping into these bounds. A genome the scenario schema or validator rejects is logged with its reason
(`rejected_by_validator`) and never simulated.

## Objectives (`models.py`)

Minimise mean delay after warm-up; maximise throughput; minimise maximum queue length; minimise near
misses (TTC events) per 1,000 vehicles that finished. A run with any collision, a reached vehicle limit
or no finished vehicle makes the candidate infeasible. **Deviations from the strategy text:** the engine
records no 95th-percentile queue and no hard-braking count, so the maximum queue and TTC near misses are
used instead. Safety proxies are model outputs, not predictions of real crashes.

## Protocol (`search.py`)

| Seed pool | Used for | Rule |
| --- | --- | --- |
| Tuning (1–3) | Fitness during the search | drawn from the search seed |
| Selection (2–5) | Choosing the shortlist from the final Pareto set | disjoint from tuning |
| Held-out (10–20) | The shortlist and the three unchanged baselines, once, after the search | disjoint from both; its hash is recorded before the search starts; reading it before the search ends raises |

Unseen conditions: the shortlist and baselines are re-run at demand ×0.8 and ×1.2 under standard and high
aggression (two held-out seeds per cell) to show where the option with the lowest mean delay changes —
a coarse indication with wide uncertainty.

Held-out comparisons are paired by seed (common random numbers): candidate minus baseline mean delay with
a 95 % percentile bootstrap interval. The report always shows every shortlisted candidate's held-out
result and flags `bestOnTuningLosesOnHeldOut` when the best tuning candidate does worse than a baseline.

## Budget, cancellation, limits (`service.py`)

The budget (population × generations × tuning seeds, plus selection, held-out and unseen-grid runs) is a
hard stop and is reserved in simulated seconds against the user's daily quota at submission; unused runs
are refunded when the search ends. At most two searches run per user. Cancellation takes effect at the
next batch boundary and leaves a consistent result marked incomplete. Every run has a fixed number of
ticks, so a run cannot hang. Searches are held in memory; the `.ufpkg` package
(`kind: discovery_search`, with the specification, the full evaluation log and the trace fingerprint) is
the durable record, and the verifier recomputes the specification and trace fingerprints.

## Acceptance (strategy §15.2.8) — status

| # | Criterion | Evidence |
| --- | --- | --- |
| D1 | Same spec + seed ⇒ same trace fingerprint | `test_same_spec_and_seed_give_the_same_trace` |
| D2 | Invalid genomes never reach the engine; reasons recorded | `test_only_validated_genomes_reach_the_evaluator`; 10,000-genome clamp fuzz `test_clamping_keeps_10000_random_genomes_within_bounds` (the full validator is exercised on 200 random genomes, not 10,000) |
| D3 | Budget never exceeded; cancel consistent within one batch | `test_the_budget_is_never_exceeded`, `test_cancel_returns_a_consistent_incomplete_result` |
| D4 | Disjoint seed pools; held-out never read before the end | `test_seed_pools_are_disjoint_and_held_out_is_sealed`, `test_held_out_seeds_are_never_used_before_the_search_ends` |
| D5 | ≥ 90 % of the known hypervolume on a synthetic problem | `test_search_reaches_90_percent_of_the_known_hypervolume` (ZDT1 on three genes) |
| D6 | Baselines equal a direct run of the same scenario | `test_baselines_equal_a_direct_run_of_the_same_scenario` (real engine) |
| D7 | A tuning winner that loses on held-out is reported | `test_a_tuning_winner_that_loses_on_held_out_is_reported` |
| D8 | Package reproduces / verifies | `test_the_package_verifies_and_tampering_is_caught`; re-running a package's specification gives the same trace (D1) |
| D9 | ≥ 3 real regimes run and reported | **Not yet done**: needs the three regime runs on the presentation machine |
| D10 | Runtime benchmark | See below; the presentation-machine benchmark is still to be recorded |

## Limitations

One four-arm junction family with one or two lanes per arm; stationary demand; uncertainty is ignored
during the search (the unseen grid only probes it); candidates are tuned to this simulator. Wall-clock
time depends on the machine and is reported as unverified in the API.

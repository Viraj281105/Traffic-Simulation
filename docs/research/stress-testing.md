# Stress Lab and Strategy Breakpoint Explorer (V3.0 W8)

`backend/src/stress/`, API `/api/v3/stress`, UI **Plan → Stress Lab**.

## Scope limit

The engine has no time-varying demand and no lane closures or incidents, so v1 stress scenarios are
**stationary extremes**. Surge and recovery scenarios need a demand-profile capability that is not built.

## Generator (`stress-v1`)

`generate(seed, count)` produces up to 30 scenarios, each reproducible from `(stress-v1, seed, index)`,
cycling through eight families: uneven directional split (1.6× / 0.4×), extreme turning (35–60 % left),
high aggression, heavy-vehicle mixes (25–40 % buses and trucks), near capacity (800–950 veh/h per arm),
over capacity (1,000–1,200 veh/h per arm), three-arm junctions (turning shares into the missing arm moved
to the remaining movements), and one to three ring lanes. Every generated scenario passes the same
validators as a user's (tested on 24 scenarios across all families).

## Failure classification (`classify.py`)

Applied to each run's own metrics; a run can carry several failures. The thresholds are this lab's stated
assumptions, not engineering standards:

| Failure | Rule |
| --- | --- |
| collision | any collision |
| gridlock | fewer than 5 % of spawned vehicles finished (at least 10 spawned) |
| vehicle_limit | the run hit the engine's vehicle limit |
| starvation | directional fairness index below 0.3 |
| excessive_queue | a queue of 20 or more vehicles |
| spillback | longest queue × 7.5 m reaches the approach length |

The suite reports, per strategy, how many scenarios had at least one failing run of each class, plus each
scenario's mean delay and failures. The signalised (metered-entry) roundabout is skipped as
`not_applicable` on three-arm scenarios; an invalid combination is skipped with the validator's reason.

## Breakpoint explorer

One scenario (default: balanced four-arm junction, 500 veh/h per arm) is run at each level of one factor
(demand scale 0.1–3.0, or driver aggression standard/moderate/high) under each strategy on the same seeds.
Per level: the mean delay of every strategy, the strategy with the lowest mean delay, and a paired seed
bootstrap of how often each strategy is lowest. A **breakpoint** is reported between two adjacent levels
whose preferred strategy differs, with the smaller of the two bootstrap shares as its confidence. Fewer than
three levels or two seeds per level is reported as "too few conditions to assess". The breakpoint lies
somewhere between the two grid points; a change between grid points can be missed.

Tests: reproducible generation, all families valid, planted failures classified, a planted flip recovered
between the right levels (0.4 → 0.6), the too-few output, an aggression sweep, a real-engine suite, API
ownership, bounds and the daily quota (`backend/tests/experiments/test_stress.py`).

## Budgets

Every job reserves `runs × duration` simulated seconds against the user's daily quota at submission
(released if the job is cancelled), at most two stress jobs run per user, at most 30 scenarios per suite and
eight levels per sweep. Jobs are held in memory.

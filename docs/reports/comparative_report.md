# Comparative Performance Report: Fixed-Time Signal vs Roundabout Control

This report documents the analytical and simulated comparison between **Fixed-Time Signal Control** and **Roundabout Yielding** strategies.

---

## 1. Executive Summary

Our comparison framework evaluates intersection performance across three traffic volume regimes (Low, Medium, and High).

*   **Roundabouts** avoid static delay — there is no red light to wait at when no competing traffic is present — and they carry low and medium demand at least as well as the signal, with a modest throughput advantage in a narrow band around $1080\,\text{veh/h}$ offered.
*   **Fixed-Time Signals** carry more traffic on average once demand approaches saturation, and do so at lower delay; under heavy oversaturation the roundabout's entry capacity is the binding constraint.
*   Measured saturation flow, single lane per approach (seed 1 peak): **signal $\approx 1540\,\text{veh/h}$, roundabout $\approx 1410\,\text{veh/h}$**; across seeds 1–5 at $4320$/$5400\,\text{veh/h}$ offered the means are $1457$/$1512$ (signal) vs $1361$/$1389$ (roundabout). The throughput crossover sits between $1080$ and $1440\,\text{veh/h}$ offered.
*   All figures were re-measured on 2026-09-24 after a bug-fix pass that changed the simulated physics (see §5 and `docs/bug-fix-report.md`).

---

## 2. Measured Capacity (V1, single lane per approach)

Method: `duration = 240 s`, `warmupTime = 30 s`, $210\,\text{s}$ measurement
window, `timeStep = 0.1`, `randomSeed = 1`, `lanesPerApproach = 1`, Poisson
arrivals, `totalVehicles = 5000` (the regression harness's setting, so the
spawner's default 200-vehicle cap can never truncate demand; no run in this
report reached its vehicle limit). "Offered" is `arrivalRate × 3600`, summed across all four
approaches. Served flow is post-warmup throughput scaled to veh/h.

| Offered veh/h | Signal served | Signal delay s | Signal maxQ | Roundabout served | Roundabout delay s | Roundabout maxQ |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 360 | 291 | 16.0 | 2 | 291 | 18.7 | 1 |
| 720 | 600 | 17.1 | 5 | 600 | 21.9 | 2 |
| 1080 | 857 | 22.2 | 9 | **874** | 25.5 | 6 |
| 1440 | **1166** | 26.7 | 12 | 1097 | 37.1 | 13 |
| 2160 | **1269** | 45.3 | 24 | 1166 | 49.2 | 15 |
| 2880 | **1543** | 51.7 | 28 | 1320 | 60.6 | 23 |
| 3600 | **1491** | 49.7 | 29 | 1354 | 71.7 | 20 |
| 4320 | 1337 | 53.7 | 30 | **1389** | 69.5 | 26 |
| 5400 | **1423** | 55.8 | 29 | 1406 | 74.3 | 26 |

**Peak served flow (seed 1): signal $1543\,\text{veh/h}$, roundabout $1406\,\text{veh/h}$.**

Saturation-regime check across seeds 1–5 (same configuration). Intervals are 95 % **Student-t** half-widths, $t_{0.975,4} = 2.776$ (revised 2026-09-25; the earlier revision used the normal 1.96 and understated them by about 29 %). Means, p-values and effect sizes are unchanged. The Welch $p$-value, not interval overlap, is the test:

| Offered veh/h | Signal served (mean ± 95% CI) | Roundabout served | Signal delay | Roundabout delay | Delay p-value |
| ---: | :--- | :--- | :--- | :--- | ---: |
| 2160 | $1313 \pm 86$ | $1269 \pm 72$ | $48.3 \pm 9.8$ s | $54.7 \pm 4.6$ s | $0.15$ |
| 4320 | $1457 \pm 206$ | $1361 \pm 29$ | $62.8 \pm 10.5$ s | $76.9 \pm 6.0$ s | $0.017$ |
| 5400 | $1512 \pm 161$ | $1389 \pm 67$ | $66.3 \pm 13.3$ s | $79.7 \pm 6.5$ s | $0.047$ |

Served-flow differences are not significant at $n=5$ ($p = 0.30 / 0.27 / 0.10$);
the signal's lower delay at $4320$ and $5400$ is.

**Zero collisions at every point, for both geometries.** Runs are
bit-identical for a fixed seed and differ across seeds.

### Reading the table

*   **Below $\approx 1080\,\text{veh/h}$** both geometries serve essentially
    all offered demand; they are not capacity-limited and the comparison is
    about delay, not throughput.
*   **The throughput crossover is between $1080$ and $1440\,\text{veh/h}$
    offered.** The roundabout is ahead at $1080$ ($874$ vs $857$); the signal
    is ahead at $1440$ and above, except on seed 1 at $4320$, where the
    roundabout is $4\%$ ahead — across seeds 1–5 the signal serves more there
    on average ($1457$ vs $1361$).
*   **Above saturation the signal carries $\approx 5$–$10\%$ more traffic on
    average** and does so at significantly lower delay, because green time is
    allocated cyclically regardless of how heavily any one approach is loaded,
    whereas roundabout entry capacity degrades as the circulating stream fills.
*   Post-saturation signal flow on one seed varies non-monotonically by up to
    $\approx 15\%$ ($1543 \to 1491 \to 1337 \to 1423$). With one shared lane
    per approach, a permissive left-turner waiting at the stop line for a gap
    in saturated opposing flow holds the whole lane, so served flow depends on
    how turners happen to arrive. That is stochastic variation in an
    oversaturated system, not a capacity cliff (see the multi-seed table).

### Scope and validity

These figures are for **one lane per approach**, which is the only
configuration in which both geometries are collision-free across their whole
working range, and is therefore the only calibrated comparison this project
supports.

**Multi-lane roundabout results must not be presented as a calibrated capacity
comparison.** With the multi-lane lock-up fix and the 2026-09-24 bug-fix pass,
measured peak served flow now rises as lanes are added — $1406 / 2040 /
2417\,\text{veh/h}$ at $1/2/3$ lanes (seed 1) — replacing the earlier
$1423 / 1234 / 943$, which were depressed by ring lock-ups. Multi-lane runs are
still not collision-free (one contact each in the 2-lane $3600$ and 3-lane
$2880\,\text{veh/h}$ runs), and the single-ring geometry still cannot express
spiral lane assignment, so these remain uncalibrated. See
[V1 Known Limitations](v1-known-limitations.md) §3.

`docs/reports/study_report.csv` (and the identical copy at the repository root, which
`.gitignore` lists but which is tracked) is the output of
`scripts/run_full_study.py --sweep-duration 240 --validation-duration 240
--num-seeds 5`: the CLI's default study scenario (one lane, one random pattern
per sweep point, 15 s / 5 s warm-up, random validation seeds). It is **one
sample** of that scenario, regenerated 2026-09-25 to replace an earlier file
that carried a retired hard-coded recommendation; its own "Evidence summary"
row states what it does and does not support. It is not the pinned calibrated
baseline above (different seeds and warm-up), so the two are not
interchangeable.

### How to read the findings in this report

| Class | Where | What it may be used for |
| :-- | :-- | :-- |
| **Calibrated, descriptive** (one seed) | §2 first table, all rows | What the calibrated configuration produced on one traffic pattern. Not evidence that a difference is more than chance |
| **Calibrated, statistically supported / not supported** (5 seeds, Welch test at α = 0.05) | §2 second table; §3 delay note | The only place a difference may be called supported. *Supported here:* signal delay lower at 4320 and 5400 veh/h (p = 0.017, 0.047). *Not supported:* every served-flow difference (p = 0.30 / 0.27 / 0.10) and every low-demand delay difference. "Not supported" means the study cannot distinguish the controls, not that they are equal |
| **Exploratory** | Multi-lane figures (§2 "Scope and validity") | Indicative only; the roundabout is modelled with one circulating lane |
| **Unmeasured expectation** | §3 fairness and idle-loss rows | Explicitly not findings |

Three metrics are tested per point without multiple-comparison correction, and
with 5 seeds the tests have little power; a supported difference at
p = 0.047 in particular should be read as marginal.

---

## 3. Performance Comparison Matrix

Throughput and delay rows are measured (§2). Fairness and 95th-percentile
queue rows are **analytical expectations that V1 has not yet measured** — the
metric pipeline computes them per run, but no multi-seed study has been run to
support a comparative claim, so they are marked as such rather than asserted.

| Metric | Low Volume ($\le 720$ veh/h) | Medium Volume ($\approx 1080$–$1440$) | High Volume ($\ge 2160$) |
| :--- | :--- | :--- | :--- |
| **Throughput** *(measured)* | Equal — both serve all demand | Roundabout ahead at $1080$; signal ahead from $1440$ | **Signal better on average** ($\approx 5$–$10\%$ more served; not significant at $n=5$) |
| **Average Delay** *(measured)* | No significant difference across seeds — see note | Signal lower on seed 1 ($22.2$ vs $25.5$ s at $1080$); not significant across seeds | **Signal lower** — significant across seeds at $4320$/$5400$ (§2) |
| **Max Queue** *(measured, seed 1)* | Roundabout marginally shorter | Comparable ($12$ vs $13$ at $1440$) | Roundabout shorter at $2160$–$5400$ |
| **Jain's Fairness Index** *(not yet measured)* | Both expected $\approx 1.0$ | Both expected $\approx 0.95$ | Signal expected higher — cyclic green guarantees each arm a turn |
| **Idle Capacity Loss** *(analytical)* | Signal has high loss | Signal has medium loss | Roundabout has minimal idle loss |

> **Note on the delay row — multi-seed result.** The classical expectation is
> that a roundabout has lower delay than a signal at low demand, because
> there is no red light to wait at when the ring is empty. A 5-seed Monte Carlo
> study (seeds $1$–$5$, identical $1$-lane / $240\,\text{s}$ / $30\,\text{s}$-warmup
> / $210\,\text{s}$-window configuration, using `src/study/validation.py`'s
> `_calculate_stats` / `_compare_groups`) was re-run on 2026-09-24:
>
> | Offered veh/h | Signal delay (mean ± 95% Student-t CI) | Roundabout delay (mean ± 95% Student-t CI) | Cohen's d | p-value | Significant? |
> | ---: | :--- | :--- | ---: | ---: | :--- |
> | 360 | $16.54 \pm 6.80$ s | $18.58 \pm 1.63$ s | $-0.51$ | $0.46$ | No |
> | 720 | $22.12 \pm 14.54$ s | $22.05 \pm 2.00$ s | $0.01$ | $0.99$ | No |
> | 1080 | $23.82 \pm 9.67$ s | $27.47 \pm 2.70$ s | $-0.64$ | $0.36$ | No |
>
> **No low-demand delay difference is supported as a finding at any of the
> three points**, as before. Signal delay is strongly seed-dependent (one seed
> reaches $42.9\,\text{s}$ at $720$); roundabout delay is tight. Throughput
> differences at these points were also not significant ($p = 0.77 / 0.40 /
> 0.78$). The roundabout's low-demand delay is $\approx 3.5\,\text{s}$ higher
> than in the previous revision because approaching vehicles now decelerate to
> `entrySpeed` over a comfortable braking distance instead of at the 9 m/s²
> hard limit (bug-fix report, BUG-7). That geometric delay is sensitive to the
> assumed approach speed ($18$–$25\,\text{m/s}$ desired speed; `roads.speedLimit`
> is not applied — see the scenario contract §2.4).

---

## 4. Analysis by Traffic Volume

### A. Low Traffic Volume
In low volume conditions, the probability of path conflicts is very small, and
both geometries serve all offered demand ($291$ and $600\,\text{veh/h}$
served at $360$ and $720$ offered).
*   **Roundabout**: Vehicles rarely yield because the circulating ring is empty.
*   **Fixed-Time Signal**: Vehicles wait at red even when no conflicting
    vehicle is present. This **Idle Opportunity Loss** is real, but at this
    demand it does not cost throughput — only delay, and across seeds that
    delay is not distinguishable from the roundabout's geometric delay.

### B. Medium Traffic Volume
As demand increases, conflicts arise and the two strategies diverge.
*   **Roundabout**: Self-organizing yielding handles demand efficiently and it
    is the better of the two at $1080\,\text{veh/h}$ offered ($874$ vs $857$
    served on seed 1; $977$ vs $960$ averaged over seeds 1–5, not significant),
    which is the one band where it leads on throughput.
*   **Fixed-Time Signal**: The fixed cycle accumulates queues on stopped arms,
    but from $1440\,\text{veh/h}$ its cyclic allocation already carries more
    traffic than the roundabout's gap acceptance ($1166$ vs $1097$).

### C. High Traffic Volume (Saturation)
At saturation the roundabout's entry capacity becomes the binding constraint.
*   **Roundabout**: Entry capacity falls as the circulating stream fills, and
    served flow plateaus near $1400\,\text{veh/h}$. A continuous circulating
    stream from a dominant approach can starve entering traffic on another,
    which is the mechanism behind the expected fairness drop.
*   **Fixed-Time Signal**: Cyclic splitting of green time guarantees every
    approach a turn regardless of load; averaged over seeds it serves
    $\approx 1450$–$1500\,\text{veh/h}$ — roughly $5$–$10\%$ above the
    roundabout — at significantly lower delay. With one shared lane, permissive
    left-turners waiting at the stop line for gaps cap how much higher it goes.

---

## 5. Revision History

*   **2026-09-25** — Evaluation-integrity pass
    (`docs/product/urbanflow-evaluation-metrics.md` §15). **No research result
    changed:** the nine-point single-seed curve was re-run at pristine `HEAD`
    and at the corrected tree and is bit-identical, and
    `test_calibrated_capacity_regression` (18 pinned values) passes unchanged;
    the seed 1–5 studies were re-run with the same procedure and reproduce
    every published mean, $p$-value and $d$ exactly. What changed is the
    **width of the 95 % confidence intervals**: they were computed with the
    normal multiplier 1.96 although the studies have 5 seeds ($t_{0.975,4} =
    2.776$), which understated them by about 29 %. The intervals in §2 and §3
    are now Student-t (roughly 1.42× wider); conclusions are unchanged
    because they rest on the Welch p-values, not on interval overlap. Also
    documented: the calibrated runs set `totalVehicles = 5000` so the default
    200-vehicle cap cannot truncate them, whereas dashboard scenarios ran with
    the cap (now sized to the scenario and flagged when reached). The
    regenerated `study_report.csv` files replace outputs that carried a retired
    hard-coded recommendation.

*   **2026-09-24** — Re-measured every figure after the bug-fix pass in
    `docs/bug-fix-report.md`, several items of which change the simulated
    physics: vehicles are no longer inserted at full speed into queues
    (BUG-1), blocked arrivals keep their turn intent (BUG-5), roundabout
    approaches decelerate at a comfortable rate instead of the hard limit
    (BUG-7), and yellow-runners and refused vehicles no longer enter the
    signalised junction without reservations (BUG-10, BUG-19 — both caused
    junction lock-ups). Effects: roundabout low-demand delay
    $+3.5\,\text{s}$ (BUG-7); signal 1-lane saturation flow lower (seed-1 peak
    $1697 \to 1543$) because a refused left-turner now waits at the stop line
    instead of stopping inside the box, which is what had produced the
    lock-ups; multi-lane roundabout capacity now rises with lanes. Conclusions
    that still hold: crossover between $1080$ and $1440$; signal ahead at
    saturation on average, with significantly lower delay there; no significant
    low-demand delay difference. Changed: the saturation advantage is
    $\approx 5$–$10\%$ (was $\approx 20\%$), and seed 1 has the roundabout
    marginally ahead at $4320\,\text{veh/h}$.

*   **2026-09-21** — Ran the 5-seed Monte Carlo validation §3's delay-row note
    called for and updated that note with the result: the single-seed delay
    reversal at $360$/$720$/$1080\,\text{veh/h}$ is **not supported** across
    seeds (not significant at any of the three points; the $360\,\text{veh/h}$
    direction actually reverses in the 5-seed mean). No other figures in this
    report changed — only the interpretation of the delay row at these three
    points. Saturation-regime claims ($\ge 2160\,\text{veh/h}$) remain
    single-seed and are unaffected by this update.
*   **2026-09-18** — Added measured capacity (§2) and rewrote §3–§4 against it.
    Signal capacity is $\approx 1700\,\text{veh/h}$; an earlier figure of
    $1800$ was measured against a junction that was already sliding into a
    gridlock defect since fixed (commit `89bb887`), and the fix's occupancy
    test is genuinely more conservative. Roundabout capacity is unchanged at
    $1423\,\text{veh/h}$. Fairness and percentile-queue claims demoted to
    explicitly unmeasured. See [V1 Known Limitations](v1-known-limitations.md).

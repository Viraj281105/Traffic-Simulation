# Comparative Performance Report: Fixed-Time Signal vs Roundabout Control

This report records the measured comparison between **fixed-time signal
control** and **roundabout yielding** under identical demand. It does not
name a universal winner: each finding is scoped to the configuration and
demand it was measured at.

---

## 1. Executive Summary

*Revision 2026-09-25b.* Every figure was re-measured after the calibration
pass (§5), which changed the simulated physics so that both junctions drive
the same vehicles under the same rules. The main conclusions reversed.
Earlier revisions are superseded.

*   **Light demand (≈ 25–30% of capacity):** the roundabout costs drivers
    less time: at 360 veh/h offered, $9.9 \pm 1.0$ s against
    $16.1 \pm 1.5$ s at the signal (5 seeds, $p < 0.001$). There is no red
    light to wait at, and entering at 18 km/h costs little once speeds follow
    the 50 km/h limit.
*   **Busy traffic (1,080 veh/h, ≈ 85% of capacity):** the roundabout
    serves more ($946$ vs $789$ veh/h, $p = 0.033$) at lower delay
    ($19.5$ vs $29.5$ s, $p = 0.040$).
*   **At and above saturation (≥ 2,160 veh/h):** the roundabout serves
    11–18% more ($p = 0.014$–$0.042$); the delay differences are not
    significant.
*   **Maximum served flow, one lane per approach (5-seed means at
    4,320–5,400 veh/h offered):** signal ≈ 1,130–1,160 veh/h, roundabout
    ≈ 1,320–1,330 veh/h. The signal's figure is specific to one **shared**
    lane with **permissive** left turns and no protected left phase: a
    left-turner waiting for a gap holds the only lane (§2 "Reading the
    table").
*   **Zero collisions** in all 90 one-lane runs (both geometries, 9 demand
    points, seeds 1–5).

---

## 2. Measured Capacity (V1, single lane per approach)

Method: `duration = 240 s`, `warmupTime = 30 s`, $210\,\text{s}$ measurement
window, `timeStep = 0.1`, `lanesPerApproach = 1`, Poisson arrivals,
`totalVehicles = 5000` (no run reached it). Both geometries use the same
vehicles: IDM $a = 2.0$, $b = 3.0\,\text{m/s}^2$, $T = 1.5$ s,
$s_0 = 2$ m, desired speed 85–105% of the 50 km/h limit, and one
lateral-acceleration limit of $3\,\text{m/s}^2$ on every curved path.
Signal: 30 s paired NS/EW greens, 4 s yellow, 2 s all-red (72 s cycle).
Roundabout: critical gap 4.0 s, follow-up 2.5 s, entry 5 m/s, circulating
≤ 8 m/s. "Offered" is `arrivalRate × 3600` summed across the four
approaches. Served flow is post-warm-up throughput scaled to veh/h.

**Seed 1 (the pinned curve, `test_calibrated_capacity_regression`):**

| Offered veh/h | Signal served | Signal delay s | Signal maxQ | Roundabout served | Roundabout delay s | Roundabout maxQ |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 360 | 240 | 17.2 | 3 | 257 | 10.2 | 1 |
| 720 | 566 | 14.6 | 4 | 600 | 12.3 | 1 |
| 1080 | 669 | 26.4 | 13 | 857 | 17.1 | 5 |
| 1440 | 1200 | 22.6 | 11 | 1063 | 29.8 | 15 |
| 2160 | 1131 | 51.6 | 25 | 1200 | 48.1 | 19 |
| 2880 | 1200 | 47.3 | 29 | 1286 | 55.0 | 15 |
| 3600 | 874 | 52.9 | 29 | 1286 | 63.4 | 22 |
| 4320 | 1149 | 49.9 | 30 | 1337 | 69.1 | 27 |
| 5400 | 1337 | 60.8 | 29 | 1354 | 68.6 | 23 |

**Seeds 1–5.** Means with 95% Student-t half-widths ($t_{0.975,4} = 2.776$);
Welch $p$-values (unpaired, no multiple-comparison correction):

| Offered veh/h | Signal served | Roundabout served | Served p | Signal delay (s) | Roundabout delay (s) | Delay p | Cohen's d (delay) |
|---:|---|---|---:|---|---|---:|---:|
| 360 | 333 ± 89 | 339 ± 79 | 0.876 | 16.1 ± 1.5 | 9.9 ± 1.0 | < 0.001 | 6.10 |
| 720 | 624 ± 61 | 689 ± 66 | 0.080 | 21.9 ± 13.8 | 13.3 ± 1.9 | 0.159 | 1.08 |
| 1080 | 789 ± 140 | 946 ± 79 | 0.033 | 29.5 ± 9.4 | 19.5 ± 1.9 | 0.040 | 1.84 |
| 1440 | 1011 ± 149 | 1131 ± 56 | 0.089 | 37.1 ± 12.3 | 31.2 ± 5.6 | 0.277 | 0.76 |
| 2160 | 1070 ± 121 | 1241 ± 85 | 0.014 | 44.3 ± 9.1 | 48.2 ± 5.8 | 0.345 | −0.64 |
| 2880 | 1159 ± 119 | 1275 ± 75 | 0.056 | 54.1 ± 6.3 | 55.5 ± 5.0 | 0.637 | −0.31 |
| 3600 | 1101 ± 167 | 1286 ± 75 | 0.034 | 62.5 ± 8.9 | 62.8 ± 2.4 | 0.944 | −0.05 |
| 4320 | 1162 ± 155 | 1323 ± 55 | 0.042 | 64.8 ± 13.2 | 65.8 ± 6.3 | 0.861 | −0.12 |
| 5400 | 1131 ± 166 | 1334 ± 57 | 0.024 | 64.3 ± 7.8 | 71.0 ± 7.6 | 0.130 | −1.07 |

**Zero collisions at every point, for both geometries, on every seed.**
Runs are bit-identical for a fixed seed.

### Reading the table

*   **Light demand.** Only the delay differs: both controls serve what
    arrives. The signal's delay is red time. The roundabout's is the time
    lost slowing to enter and to circulate, now about 7–10 s.
*   **Where the roundabout is ahead on throughput.** From about 1,080 veh/h
    the roundabout serves more on average. The difference is supported at
    1,080 and at 2,160 and above; at 1,440 and 2,880 it is not ($p = 0.089$,
    $0.056$). Seed 1 at 1,440 has the signal ahead, which shows how large the
    signal's seed-to-seed spread is (±149 veh/h).
*   **Why the signal saturates early.** There is one lane per approach,
    shared by all movements, and no protected left phase. A left-turner who
    must wait for a gap in the opposing flow holds the whole lane. Now that
    turns are taken at a physically possible speed, that left-turner also
    spends longer in the junction. There is no in-box waiting position (in-box
    waiting produced the BUG-19 lock-ups), so this is conservative compared
    with HCM shared-lane practice. A dedicated left lane (2 lanes per approach)
    raises the signal's served flow to ≈ 2,400–2,500 veh/h (§2 "Scope and
    validity").
*   **Delay at saturation** is not distinguishable between the controls:
    both are queue-bound.

### Scope and validity

These figures are for **one lane per approach**, the configuration in which
both geometries are collision-free across the whole demand range.

**Multi-lane results are exploratory, not calibrated.** Both geometries model
every lane: the signal gets per-movement lanes and the roundabout one
circulating ring per entry lane. Capacity rises with lanes for both (3-seed
means at 4,320–5,400 veh/h: signal ≈ 2,460 / 3,100 veh/h, roundabout
≈ 1,900 / 2,150 veh/h for 2 / 3 lanes). The roundabout has no lane markings,
though, so a driver leaving from an inner ring crosses the outer ring; 5 of
54 multi-lane roundabout runs had a contact (2 below saturation). The old
statement that the roundabout is modelled with a single circulating lane was
wrong and has been removed.

**Reference capacity for demand levels.** The product's demand levels are
shares of the mean of both controls' maximum served flow per lane count:
1,250 / 2,180 / 2,620 veh/h for 1 / 2 / 3 lanes
(`study/calibration.py::REFERENCE_CAPACITY_VPH`).

`docs/reports/study_report.csv` (and the identical root copy) is one run of
`scripts/run_full_study.py` at its defaults: one lane, 240 s sweep tiers and
validation runs, 30 s warm-up. It is one sample of that scenario, and its
own "Evidence summary" row states what it supports.

### How to read the findings in this report

| Class | Where | What it may be used for |
| :-- | :-- | :-- |
| **Calibrated, descriptive** (one seed) | §2 first table | What the calibrated configuration produced on one traffic pattern |
| **Calibrated, statistically supported / not supported** (5 seeds, Welch at α = 0.05) | §2 second table | *Supported:* roundabout delay lower at 360 and 1,080 veh/h; roundabout served flow higher at 1,080 and at 2,160–5,400 veh/h. *Not supported:* every other difference, including all delay differences at 1,440 veh/h and above. "Not supported" means this study cannot distinguish the controls, not that they are equal |
| **Exploratory** | Multi-lane figures (§2 "Scope and validity") | Indicative only |

Three metrics are compared per point without multiple-comparison
correction, and five seeds give little power. Differences with $p$ between
0.03 and 0.05 should be read as marginal.

---

## 3. Performance Comparison Matrix

| Metric | Light ($\le 720$ veh/h) | Busy ($\approx 1080$–$1440$) | Saturated ($\ge 2160$) |
| :--- | :--- | :--- | :--- |
| **Throughput** *(measured, 5 seeds)* | Equal: both serve all demand | Roundabout higher at 1,080 ($p = 0.033$); not supported at 1,440 | Roundabout higher (11–18%, supported at 2,160, 3,600, 4,320 and 5,400) |
| **Average delay** *(measured, 5 seeds)* | Roundabout lower at 360 ($p < 0.001$); not supported at 720 | Roundabout lower at 1,080 ($p = 0.040$) | No supported difference |
| **Max queue** *(measured, seed 1)* | Roundabout shorter | Roundabout shorter at 1,080; longer at 1,440 | Roundabout shorter |
| **Fairness, idle loss** | Computed per run, not studied across seeds; no comparative claim | | |

---

## 4. Analysis by Traffic Volume

### A. Light traffic
Both controls serve all offered demand. The signal makes drivers who arrive
on red wait even when no one else is there. The roundabout makes every driver
slow to about 18 km/h to enter and 24 km/h around the ring, but rarely makes
anyone stop. With equal speed assumptions, the second costs less
(≈ 6 s per driver at 360 veh/h).

### B. Busy traffic
Queues form at the signal's red approaches and clear in bursts; the shared
lane lets a single left-turner hold back the vehicles behind it. The
roundabout's gap acceptance keeps entries moving while circulating flow is
moderate, and at 1,080 veh/h it serves more at lower delay.

### C. Saturation
Both junctions are at capacity and delay is queue-bound for both. With one
shared lane and permissive lefts, the signal's served flow plateaus near
1,100–1,160 veh/h, and the roundabout's near 1,300–1,330 veh/h, where
entry capacity falls as the ring fills. A signal with a separate left-turn
lane or a protected left phase would behave differently; it is not modelled
in the calibrated configuration.

---

## 5. Revision History

*   **2026-09-25b**: calibration pass (`docs/bug-fix-report.md` BUG-21
    to BUG-25; `docs/product/urbanflow-evaluation-metrics.md` §17). **Physics
    changed, and every result in §1–§4 was re-measured; the main conclusions
    reversed.** Causes:
    (1) `roads.speedLimit` is now applied, so desired speeds are 85–105% of
    50 km/h instead of 18–25 m/s;
    (2) one lateral-acceleration limit (3 m/s²) now applies to every curved
    path, where signal turns previously had none;
    (3) the roundabout's entry-speed zone is 10 m instead of 60 m;
    (4) entering drivers no longer give way to vehicles that leave the ring
    before reaching them.
    Effects: roundabout light-demand delay about halves (19.2 → 10.1 s at
    360 veh/h, 3-seed mean), and 1-lane signal served flow at saturation
    falls by about 20% (1,537 → 1,194 veh/h at 5,400 veh/h, 3-seed mean),
    because turning vehicles now slow for the curve and a waiting
    left-turner holds the only lane longer. Superseded: "signal carries 5–10%
    more at saturation, at significantly lower delay" and "no significant
    low-demand delay difference". The before/after matrix (1–3 lanes × 9
    demands × 3 seeds × 2 geometries, 162 runs each) is summarised in
    `docs/bug-fix-report.md`. Test pins re-measured:
    `test_calibrated_capacity_regression` (curve and ordering).

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

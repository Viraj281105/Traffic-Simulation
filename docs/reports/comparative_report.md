# Comparative Performance Report: Fixed-Time Signal vs Roundabout Control

This report documents the analytical and simulated comparison between **Fixed-Time Signal Control** and **Roundabout Yielding** strategies.

---

## 1. Executive Summary

Our comparison framework evaluates intersection performance across three traffic volume regimes (Low, Medium, and High).

*   **Roundabouts** avoid static delay — there is no red light to wait at when no competing traffic is present — and they carry low and medium demand at least as well as the signal, with a modest throughput advantage in a narrow band around $1080\,\text{veh/h}$ offered.
*   **Fixed-Time Signals** carry substantially more traffic once demand approaches saturation, and they keep serving it under heavy oversaturation where the roundabout's entry capacity is the binding constraint.
*   Measured saturation capacity, single lane per approach: **signal $\approx 1700\,\text{veh/h}$, roundabout $\approx 1423\,\text{veh/h}$.** The throughput crossover sits between $1080$ and $1440\,\text{veh/h}$ offered.

---

## 2. Measured Capacity (V1, single lane per approach)

Method: `duration = 240 s`, `warmupTime = 30 s`, $210\,\text{s}$ measurement
window, `timeStep = 0.1`, `randomSeed = 1`, `lanesPerApproach = 1`, Poisson
arrivals. "Offered" is `arrivalRate × 3600`, summed across all four
approaches. Served flow is post-warmup throughput scaled to veh/h.

| Offered veh/h | Signal served | Signal delay s | Signal maxQ | Roundabout served | Roundabout delay s | Roundabout maxQ |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 360 | 291 | 16.0 | 2 | 291 | 15.1 | 1 |
| 720 | 600 | 15.6 | 4 | 600 | 18.9 | 2 |
| 1080 | 891 | 21.6 | 7 | **926** | 25.2 | 4 |
| 1440 | **1234** | 29.9 | 9 | 1080 | 31.6 | 15 |
| 2160 | **1474** | 39.2 | 19 | 1286 | 48.6 | 25 |
| 2880 | **1629** | 40.6 | 46 | 1320 | 61.9 | 37 |
| 3600 | **1629** | 58.0 | 55 | 1371 | 70.9 | 60 |
| 4320 | **1543** | 68.2 | 71 | 1423 | 70.6 | 78 |
| 5400 | **1697** | 72.4 | 87 | 1389 | 81.0 | 81 |

**Peak served flow: signal $1697\,\text{veh/h}$, roundabout $1423\,\text{veh/h}$.**

**Zero collisions at every point, for both geometries.** Runs are
bit-identical for a fixed seed and differ across seeds.

### Reading the table

*   **Below $\approx 1080\,\text{veh/h}$** both geometries serve essentially
    all offered demand; they are not capacity-limited and the comparison is
    about delay, not throughput.
*   **The throughput crossover is between $1080$ and $1440\,\text{veh/h}$
    offered.** The roundabout is ahead at $1080$ ($926$ vs $891$); the signal
    is ahead at $1440$ and everywhere above.
*   **Above saturation the signal carries $\approx 20\%$ more traffic** and
    does so at lower delay, because green time is allocated cyclically
    regardless of how heavily any one approach is loaded, whereas roundabout
    entry capacity degrades as the circulating stream fills.
*   Post-saturation signal flow varies non-monotonically by roughly $10\%$
    ($1629 \to 1543 \to 1697$). That is ordinary stochastic variation in an
    oversaturated queueing system on a single seed, not a capacity cliff.

### Scope and validity

These figures are for **one lane per approach**, which is the only
configuration in which both geometries are collision-free across their whole
working range, and is therefore the only calibrated comparison this project
supports.

**Multi-lane roundabout results must not be presented as a calibrated capacity
comparison.** Measured peak served flow falls as lanes are added — $1423 /
1234 / 943\,\text{veh/h}$ at $1/2/3$ lanes — where published multi-lane
roundabout capacity rises. The single-ring geometry cannot express spiral lane
assignment, so added lanes contribute weaving conflicts faster than capacity.
This is a documented V2.0 scope limitation, not a calibration error. See
[V1 Known Limitations](v1-known-limitations.md) §3.

---

## 3. Performance Comparison Matrix

Throughput and delay rows are measured (§2). Fairness and 95th-percentile
queue rows are **analytical expectations that V1 has not yet measured** — the
metric pipeline computes them per run, but no multi-seed study has been run to
support a comparative claim, so they are marked as such rather than asserted.

| Metric | Low Volume ($\le 720$ veh/h) | Medium Volume ($\approx 1080$–$1440$) | High Volume ($\ge 2160$) |
| :--- | :--- | :--- | :--- |
| **Throughput** *(measured)* | Equal — both serve all demand | Roundabout ahead at $1080$; signal ahead from $1440$ | **Signal is clearly better** ($\approx 20\%$ more served) |
| **Average Delay** *(measured, seed 1)* | Roundabout lower at $360$; signal lower at $720$ — see note | Signal lower ($21.6$ vs $25.2$ s at $1080$) | **Signal lower** ($40.6$ vs $61.9$ s at $2880$) |
| **Max Queue** *(measured)* | Roundabout marginally shorter | Signal shorter ($9$ vs $15$ at $1440$) | Comparable; roundabout shorter at $2880$ |
| **Jain's Fairness Index** *(not yet measured)* | Both expected $\approx 1.0$ | Both expected $\approx 0.95$ | Signal expected higher — cyclic green guarantees each arm a turn |
| **Idle Capacity Loss** *(analytical)* | Signal has high loss | Signal has medium loss | Roundabout has minimal idle loss |

> **Note on the delay row.** The classical expectation is that a roundabout
> has lower delay than a signal at low demand, because there is no red light
> to wait at when the ring is empty. The measurements hold that at
> $360\,\text{veh/h}$ ($15.1$ vs $16.0$ s) but reverse it at $720$ and
> $1080$. This is a **single-seed** result and the differences are a few
> seconds, so it is reported rather than concluded: confirming or overturning
> it needs the multi-seed Monte Carlo path in `src/study/validation.py`, which
> has not been run for this comparison. Do not present the reversal as a
> finding until it has been.

---

## 4. Analysis by Traffic Volume

### A. Low Traffic Volume
In low volume conditions, the probability of path conflicts is very small, and
both geometries serve all offered demand ($291$ and $600\,\text{veh/h}$
served at $360$ and $720$ offered).
*   **Roundabout**: Vehicles rarely yield because the circulating ring is empty.
*   **Fixed-Time Signal**: Vehicles wait at red even when no conflicting
    vehicle is present. This **Idle Opportunity Loss** is real, but at this
    demand it does not cost throughput — only delay, and by a margin of about
    a second at $360\,\text{veh/h}$.

### B. Medium Traffic Volume
As demand increases, conflicts arise and the two strategies diverge.
*   **Roundabout**: Self-organizing yielding handles demand efficiently and it
    is the better of the two at $1080\,\text{veh/h}$ offered ($926$ vs $891$
    served), which is the one band where it leads on throughput.
*   **Fixed-Time Signal**: The fixed cycle accumulates queues on stopped arms,
    but from $1440\,\text{veh/h}$ its cyclic allocation already carries more
    traffic than the roundabout's gap acceptance ($1234$ vs $1080$).

### C. High Traffic Volume (Saturation)
At saturation the roundabout's entry capacity becomes the binding constraint.
*   **Roundabout**: Entry capacity falls as the circulating stream fills, and
    served flow plateaus near $1400\,\text{veh/h}$. A continuous circulating
    stream from a dominant approach can starve entering traffic on another,
    which is the mechanism behind the expected fairness drop.
*   **Fixed-Time Signal**: Cyclic splitting of green time guarantees every
    approach a turn regardless of load, and served flow continues to rise to
    about $1700\,\text{veh/h}$ — roughly $20\%$ above the roundabout — at
    consistently lower delay.

---

## 5. Revision History

*   **2026-09-18** — Added measured capacity (§2) and rewrote §3–§4 against it.
    Signal capacity is $\approx 1700\,\text{veh/h}$; an earlier figure of
    $1800$ was measured against a junction that was already sliding into a
    gridlock defect since fixed (commit `89bb887`), and the fix's occupancy
    test is genuinely more conservative. Roundabout capacity is unchanged at
    $1423\,\text{veh/h}$. Fairness and percentile-queue claims demoted to
    explicitly unmeasured. See [V1 Known Limitations](v1-known-limitations.md).

# Preview rehearsal kit — PV-1, Thursday 29 October 2026

> **Purpose:** the working sheet for task B0-4 ([#173](https://github.com/Viraj281105/Traffic-Simulation/issues/173)). Rehearsal 1 is Tue 27 Oct, Rehearsal 2 is Wed 28 Oct. Source of truth for content: [V3 presentation plan §2](V3_PRESENTATION_PLAN.md#2-preview--thursday-29-october-2026). Decision D-PV = PV-1 (2026-10-14).
> **Status:** prepared 2026-10-14 for the rehearsals. Nothing in it has been rehearsed yet.
> **Gates it serves:** G-PF (Tue 27 Oct 12:00), G-PV (Wed 28 Oct 17:00: two rehearsals ≤ 14 min, one cold start with the network disabled).

---

## 1. Run of show (14:00 + 6:00 Q&A)

| Time | Segment | Live or recorded | Fallback level |
| --- | --- | --- | --- |
| 0:00–1:30 | Status slide: V2.0 gate result, V3.0 in one line, what is not claimed | Slide | — |
| 1:30–4:30 | Planner: build and run the small study | **Live, bounded** | F1 open the precomputed study by id |
| 4:30–7:30 | Planner: read the evidence (intervals, a tie shown as inconclusive, findings, validity banner, caveats) | Precomputed | Static capture |
| 7:30–9:30 | Provenance and Reproduce (commit, fingerprints, seeds) | Live | Recorded clip |
| 9:30–10:30 | Protection of data (recorded gate test output) | Slide | — |
| 10:30–11:30 | Export JSON / Markdown / CSV (state: `.ufpkg` is planned) | Live download | Files on disk |
| 11:30–13:30 | V3.0 design walkthrough (conditions vs replications vs runs; win/tie/loss and regret; manifest and replay classes; funding table) | Slides | — |
| 13:30–14:00 | Limits and the ask | Slide | — |
| 14:00–20:00 | Q&A | | |

**Must say aloud (segment 2):** the intervals describe seed-to-seed variation for one scenario, **not** uncertainty about demand or driver behaviour.

**Optional (PV-2 only):** the sampler condition table, labelled "design prototype — no simulation results" (inside 11:30–13:30, ≤ 1 minute).

## 2. Live-run rule and what we measured

The live segments run only if the study takes **≤ 45 s on three consecutive runs on the presenting machine**.

| Study | Measured 2026-10-14 (development machine, 3 runs, mean) | Verdict for the live slot |
| --- | --- | --- |
| Small: 60 s sim, 1 demand level, 3 seeds (9 simulations) | 2.02 s | Live |
| Medium: 300 s sim, 3 demand levels, 3 seeds (27 simulations) | 39.76 s (max 40.15 s) | Passes the 45 s rule by a thin margin; keep **precomputed** |

Repeat the three-run timing on the presenting machine at the start of Rehearsal 1 and record it in §6. Source: B0-1 timings on #173.

## 3. Pre-flight checklist (before each rehearsal)

- [ ] On the frozen preview commit: `git rev-parse HEAD` = ______ (matches the pack manifest)
- [ ] Fallback pack regenerated on that commit: `python scripts/build_fallback_pack.py http://localhost:8765 fallback-pack`; `SHA256SUMS` verified (`sha256sum -c`)
- [ ] Backend starts cold with `DEV_AUTH_BYPASS=1`; production frontend build served locally
- [ ] Time to first usable page after a cold start: ______ s
- [ ] Network **disabled** (Rehearsal 2 and one drill in Rehearsal 1); fonts fall back cleanly; layout checked
- [ ] Precomputed study opens by id after a reload
- [ ] Recorded video plays from local disk and from the USB stick
- [ ] Backup laptop has the repository, the pack and the video
- [ ] One-pager printed from the final draft
- [ ] Slides open without network; font and image checks done
- [ ] Notifications off, power settings set to never sleep, display scaling checked on the projector

## 4. Acceptance checks PA-1 … PA-7 (PV-1 forms) — run once on the presenting machine

| # | Must prove | How to show | Pass? |
| --- | --- | --- | :-: |
| PA-1 | A study is submitted through the planner **and** the documented API | Planner run; then `scripts/v2_demo.py`-style API call | ☐ |
| PA-2 | The same study opens by id after a reload | Reload, open by id | ☐ |
| PA-3 | Intervals, tie handling, validity banner, caveats; labelled seed-to-seed | Read the results page aloud | ☐ |
| PA-4 | Export works and `reproduce` verifies; `.ufpkg` not claimed | Download three formats; press Reproduce | ☐ |
| PA-5 | Commit, fingerprints, seeds visible | Provenance panel | ☐ |
| PA-6 | A deliberately failing job shows its error; job cap explained; cancellation stated unsupported | See §5 drill D6 | ☐ |
| PA-7 | Precomputed study, exports and video exist, are checksummed, from the preview commit, and the fallback was used in a rehearsal | Pack + checksums + drill log | ☐ |

## 5. Failure drills (exercise every fallback level; an untested fallback is not a fallback)

| Drill | Trigger | Action | Rehearsal | Done |
| --- | --- | --- | --- | :-: |
| D1 | **F1** live run exceeds 45 s or errors | Say "here is one I ran earlier"; open the precomputed study by id | 1 and 2 | ☐ |
| D2 | **F2** UI fails | Show exported JSON/Markdown and the API response in a terminal | 2 | ☐ |
| D3 | **F3** backend will not start | Play the recorded video; show the checksums | 2 | ☐ |
| D4 | **F4** laptop fails | Switch to the backup laptop or the USB video | 2 | ☐ |
| D5 | Network disabled at cold start | Whole flow offline; fonts and layout check | 2 | ☐ |
| D6 | Failing job (PA-6) | Submit an invalid or oversized study; read the error. Note: the live backend already answers a second concurrent run with `429 SIMULATION_LIMIT_REACHED` ("A simulation you started is still running…") — use that to explain the job cap; state aloud that cancellation is **not supported** in V2.0 | 1 | ☐ |

## 6. Rehearsal log (copy one block per rehearsal)

```
Rehearsal #: __   Date/time: __________   Machine: __________   Commit: __________
Cold start (s): ____   Network: on / OFF
Small-study timings (3 runs, s): ____ ____ ____   all ≤ 45 s? Y / N
Segment times (target in brackets):
  Status [1:30] ____   Build+run [3:00] ____   Evidence [3:00] ____   Provenance [2:00] ____
  Data protection [1:00] ____   Export [1:00] ____   V3.0 walkthrough [2:00] ____   Limits [0:30] ____
Total (≤ 14:00 incl. one fallback switch): ______
Drills done: D1 ☐  D2 ☐  D3 ☐  D4 ☐  D5 ☐  D6 ☐
Defects found / fixes: ____________________________________________
Questions asked (see §7) and weak answers: ____________________________
Go / no-go for G-PV: ______
```

## 7. Hardest expected questions (honest answers prepared in the presentation plan §2.7)

1. "Is it calibrated to real traffic?" — No. A calibration framework exists; no real observations have been run; no tuning exists.
2. "What uncertainty do the intervals show?" — Seed-to-seed variation for one scenario. Parameter uncertainty is the planned Robustness Lab, not built.
3. "Is the public site running this?" — Not verified; production deployment is a separate, authorised step (G-PROD).
4. "Why isn't the V3.0 demo live?" — V3.0 implementation starts only after the design-approval gate; this preview shows V2.0 plus the design.
5. "Does the roundabout win?" — UrbanFlow does not rank; here are the intervals and the conditions.
6. "Is my data private?" — Per-user ownership is tested; show the recorded test output.

*Ask a second person to put these to you in Rehearsal 2 if possible.*

## 8. Go / no-go inputs for G-PV (Wed 28 Oct 17:00)

- [ ] Two rehearsals ≤ 14 min, one cold-start and offline
- [ ] Benchmark recorded (done 2026-10-14 on the development machine; repeat on the presenting machine)
- [ ] Backend and frontend suites green on the preview commit
- [ ] Every claim on the slides appears in the claims register
- [ ] Fallback ladder F0–F4 exercised

If a rehearsal overruns or a live step fails twice, drop that step to its fallback in the plan rather than retrying on the day.

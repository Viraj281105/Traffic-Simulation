# UrbanFlow — Live Demo Script

**Length:** about 15 minutes (12 minutes if you skip the Research lab tour). **Audience:** planning officers and technical reviewers. **Tagline:** *Signal or roundabout? Try both.*

> UrbanFlow shows evidence, not a verdict. Say this early and repeat it at the end.

---

## 0. Before you start (5 minutes, off-camera)

| Check | How |
| --- | --- |
| App is running | Open `http://localhost:5173/` (dev stack) or `http://localhost/` (Docker). The landing page must load. |
| Backend is healthy | `http://localhost:8000/health` returns `{"status":"healthy"}`. |
| Signed in | Dev stack shows a **DEV AUTH** chip, so no login is needed. A production build asks for sign-in when you open the **Research lab** or press **Save**. |
| Browser | Light theme, 100% zoom, full screen. Close other tabs. |
| Saved runs | Open **Saved** once. Delete stray test runs so the demo list is clean. |
| Warm up the lab | Open **Research lab → Three-way study** and start it before you present. It runs 90 simulations and takes several minutes. Keep that tab open. |

**Numbers change.** Each run draws a random traffic pattern, and **Start over** picks a new one. Do not read figures from this script. Read the numbers on screen. To make a run repeatable, set the seed under **Advanced settings → Random seed**. A fixed seed reproduces the same traffic.

**Speed.** The simulation plays in real time. Use the **4x** button in the playback bar so a 5-minute run takes about 75 seconds.

---

## 1. Landing page — the pitch (1.5 min)

**Open:** `/`

**Do:**
1. Pause on the hero: **"Signal or roundabout? Try both."**
2. Point at the three facts under the buttons: *3 steps*, *Same cars for both*, *No verdict: your call*.
3. Scroll to **01 / The premise**: two cards, *Signal control* and *Roundabout control*.
4. Scroll to **02 / How it works**: four cards (Describe your junction, Watch both run, Read the results, Check and compare).
5. Scroll to **03 / What you learn**: plain-language questions on the left, specialist tools on the right.
6. Optional: click the moon icon to show dark mode.

**Say:**
> "A junction on your street is up for redesign: keep the traffic lights, or build a roundabout? People argue from opinion. UrbanFlow turns that into a fair test. It runs both options on the same virtual junction with exactly the same cars, then tells you in plain language what happened, why, and how sure you can be. It never picks a winner. The decision stays with you."

**Click:** **Compare your junction**.

---

## 2. Compare, Step 1 — Describe the junction (2 min)

**Page:** `/app/comparative`. The step bar at the top shows **1 Your junction → 2 Watch both run → 3 Results**.

**Do and say, question by question:**

| Question | What to show | Talking point |
| --- | --- | --- |
| 1. How busy is the junction? | Six cards from **Light** (310 veh/h) to **Over capacity** (1,630 veh/h). Select **Busy**. | "Levels are relative to what a one-lane junction can carry, so 'busy' means the same thing at every lane count." |
| 2. How many lanes? | **1 / 2 / 3 lanes**. Leave on **1**. Briefly click **2** to show the caution note, then go back to **1**. | "One lane per approach is the calibrated case. More lanes are flagged as indicative." |
| 3. What traffic? | **Cars only**, **Typical city mix**, **Bus & freight route**, **Many two-wheelers**. | "Buses, trucks and motorcycles each drive differently. The calibrated comparison is cars only." |
| 4. Signal behaviour | **On a fixed timetable** or **Responds to traffic**. | "Fixed timer versus detectors that give green where cars are waiting." |
| 5. Driver behaviour | **Structured** or **Unstructured / Chaotic**. | "Idealised drivers or realistic hesitation and blocking." |
| 6. How long to watch? | **Quick look** (2 min), **Standard** (5 min), **Thorough** (10 min). Select **Standard**. | "The first 30 seconds are a warm-up and are not counted." |

**Then show the depth:**
1. Scroll to **The two options being compared**. Read the signal timetable (30 s green, 72 s cycle) and the roundabout rule (gap of at least 4.0 s).
2. Click **Advanced settings**. Show presets, signal timing, roundabout gap, and **Random seed**. Set the seed to a fixed number if you want repeatable numbers. Click **Use these settings**.
3. Scroll to the top and click **Build your own junction**. Show the six-step builder: junction type, roads and lanes with lane arrows, traffic per road, vehicle mix, simulation, advanced presets. Say: *"Same tool, full control: T-junctions, lane arrows, per-road demand, import and export."* Click **Answer a few questions** to go back.

**Click:** **Run the comparison →**

---

## 3. Compare, Step 2 — Watch both run (2.5 min)

**Important:** the page opens in a **Ready** state. **Press Play** in the playback bar. The text says "Press Play below to start both junctions at once."

**Do:**
1. Click **Play**, then **4x**.
2. Point at the two maps: **Traffic signal** and **Roundabout**. On a narrow window they stack. On a wide screen they sit side by side.
3. Point at the live panel: progress bar (`0:31 of 5:00`), the shaded warm-up section, and the three live rows: **Vehicles waiting now**, **Got through so far**, **Time lost per driver so far**.
4. Read **What to look for**: queues build on red and clear in bursts, versus drivers slowing and waiting for a gap.
5. Click **Show specialist live charts & all metrics**. Show the tabs Flow, Performance, Queues, Safety, Capacity, Table. Click **← Back to the simple view**.
6. Point at the playback bar: **Play / Pause / Start over**, speed buttons, **Simulated time**, **Status**.

**Say:**
> "Both maps receive the same vehicles at the same moments. Only the control differs. The warm-up lets traffic build from an empty road, so early numbers are not counted."

**Tip:** you can click **See results so far →** once the warm-up is over. Wait for **Finished** if you can.

**Click:** **See your results →**

---

## 4. Compare, Step 3 — Results (3.5 min)

**Page:** the results report. Walk it top to bottom.

| Section | What to say |
| --- | --- |
| **Scenario chips** (traffic level, lanes, mix, signal, duration, traffic pattern number) | "Everything needed to reproduce this run." |
| **In short** | Read the three bullets aloud. "It states both values and says which was lower. Then it says it does not pick a winner." |
| **How much time do drivers lose?** | Show the paired bars, the A–F grade ("Is that a lot of time lost?"), and open **How is this measured?** "Time lost is not the same as waiting. It includes slowing the layout forces." |
| **How much traffic gets through?** | "Same arrivals, so a difference means one cleared traffic faster." |
| **How long do queues get?** | Typical queue, longest queue, time with more than 5 vehicles queued. |
| **Is every direction treated alike?** | Fairness band in words, with the index. |
| **Why did this happen?** | Read one or two items, for example how the signal and the roundabout decide who goes, or idle green on the signal. |
| **How reliable is this?** | Read the fairness note and the "Not modelled" note: pedestrians, cyclists, crash risk. "We say what the model cannot do." |

### The key moment: the reliability check

1. In **How reliable is this?**, keep **5 (recommended)** and click **Check reliability**. It takes about 10 seconds for a short run.
2. Read the headline and the table (**Consistent difference**, **Not consistent — could be chance**, or **About the same**), plus the **Lower at** tally.
3. Open **Show the statistics**: means with 95% intervals, p-values, Cohen's d, per-seed table.

**Say:**
> "One run is one traffic pattern. In my rehearsal a single run showed the signal about 5 seconds better, but across five new patterns the difference was not consistent. That is exactly why we repeat the test. Your numbers will differ, so read your own headline."

### Try another scenario

1. Click **Try busier traffic**. A new comparison starts for the next demand level. Press Play and use 4x if you want to show it, or skip ahead.
2. Point at the table **Scenarios you have run this session**: time lost, vehicles through, longest queue for each run.
3. Click **Save this comparison**. A toast confirms the save.

### Specialist layer

1. Scroll down and expand **All measurements & method (for specialists)**.
2. Show the method list (IDM driver model, Poisson arrivals, 50 km/h limit, warm-up, signal plan, roundabout gap).
3. Click **Open charts & user-weighted scoring**. Show the charts and the weighted score with presets **Balanced / Throughput first / Delay first / Equal weights**. Say: "The score reflects your priorities, not an objective ranking." Press **Escape** to close.
4. Click **Download all metrics (CSV)**.

---

## 5. Saved — reproducibility (1.5 min)

**Click:** **Saved** in the top bar. Page `/app/history`.

**Do:**
1. Show the table: saved time, run ID, name, type, seed, commit, config (**Exact**), simulated time, average delay and vehicles served as *signal / roundabout*.
2. Click a run name to open its own page. Show **Re-run and export** (**Open in simulator**, **Compare with other runs**, **Export JSON**, **Export CSV**), the **Reproducibility** panel (run ID, seed, git commit, Python version, time step, duration, warm-up), **Verify reproduction (headless)**, **Notes and tags**, the stored metrics, and the stored configuration.
3. Go back, tick two runs, click **Compare selected (2)**. Show **Settings that differ** and the metric table with differences against a baseline run. Point out the warnings about different seeds or code versions.

**Say:**
> "Every saved run keeps its exact configuration, seed, timing and code version, so anyone can reproduce it or audit it later."

---

## 6. Research lab (3 min)

**Click:** **Research lab**. A sub-navigation bar appears: Overview, Your own junction, Three-way study, Statistical validation, Traffic-level sweep, Signal on its own, Roundabout on its own.

| Tab | What to show | Say |
| --- | --- | --- |
| **Overview** | The seven-stage "How a study proceeds" diagram, the three control strategies, the metric gallery, the **Why one run is not enough** widget (click **After 3 runs / After 10 runs**), and the evidence ladder. | "Inconclusive is a result of its own. It is not 'no difference'." |
| **Your own junction** | The preset "Typical urban junction", the controls to compare (fixed signal, adaptive signal, roundabout), seeds and demand multipliers. Click **Run the study**. | "Any junction the model supports, run under every control on matched seeds." After about 1.5 minutes: show the delay table with 95% intervals, the readings (for example *Roundabout lower*, *Inconclusive*), the by-approach and by-vehicle-class tables, and the CSV and JSON downloads. |
| **Three-way study** | The pre-started run, plus the matched-seeds diagram and the worked example of how a reading is classified (tie check, then interval). | "Same seeds across three controls. The method is stated, with its limits." |
| **Statistical validation** | Click **Launch Quick Check** (3 seeds, about 25 s). Show the verdict (for example *No statistically supported difference*), the per-metric cards with Cohen's d and p-value, and the charts. Then click **Run integrity check**. | "The integrity check confirms no vehicles are lost or created, no conflicting greens, and that a seed reproduces its results." |
| **Traffic-level sweep** | Click **Load Past Sweep** and choose one. Show the crossover bracket ("where the lower-delay control changes"), the tier tally, the delay curve with the **Crossover** marker, and the **Demand Explorer**. | "Which option is better depends on traffic. Here is where the answer flips." Running a new sweep takes minutes, so use a saved one. |
| **Signal on its own** / **Roundabout on its own** | Click **Play**, then **4x**. Show stop lines, queue labels, the live phase text, the full metric panel, **Scenario settings**, **Save to History**. | "For specialists: one control, every metric." |

---

## 7. Close (30 seconds)

**Say:**
> "UrbanFlow turns 'signal or roundabout?' into a fair, repeatable test. Same cars, both options, plain-language answers with the numbers visible, the reason behind them, an honest reliability check, and the limits stated up front. Calibrated for one lane with cars; everything else is labelled indicative. It shows the evidence. The decision stays with you."

**Click:** the **UrbanFlow** logo to return to the landing page.

---

## Appendix A — Timing plan

| Segment | Minutes |
| --- | --- |
| 1. Landing | 1.5 |
| 2. Step 1 Describe | 2 |
| 3. Step 2 Watch | 2.5 |
| 4. Step 3 Results and reliability | 3.5 |
| 5. Saved | 1.5 |
| 6. Research lab | 3 |
| 7. Close | 0.5 |
| **Total** | **about 14.5** |

## Appendix B — If something goes wrong

| Problem | Fix |
| --- | --- |
| Page says "Loading…" for a few seconds | Wait. Routes load on first open. |
| Step 2 sits at **Ready** | Press **Play**. The scenario starts only when you press it. |
| **See results so far** is greyed out | The warm-up is not over yet, or no vehicle has got through. Wait a few more seconds. |
| Reliability check or study fails | Check `http://localhost:8000/health`. Restart the backend and retry. |
| Numbers differ from your rehearsal | Expected. Set a fixed **Random seed** in Advanced settings, or narrate what is on screen. |
| Sign-in prompt on Research lab or Save (production build) | Sign in with your demo account. |
| A study takes too long | Use **Load Past Sweep**, or a 3-seed, 2-minute setting. |

## Appendix C — What not to claim

- UrbanFlow does **not** say one design is better everywhere.
- Calibration is against UrbanFlow's own measured capacity, **not** observed traffic.
- Safety figures (TTC, PET) are exploratory surrogates, not crash risk.
- There is no emissions or fuel model, and pedestrians and cyclists are not modelled.
- Multi-lane and mixed-vehicle results are **indicative**, not calibrated.

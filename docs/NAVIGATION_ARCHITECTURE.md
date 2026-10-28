# UrbanFlow navigation architecture (audit and proposal)

Status: implemented on `viraj-dev`, uncommitted (2026-10-28).

## 1. Current hierarchy (before)

The dashboard is one document (`app.html`) with a hand-rolled router
(`frontend/src/routing.ts`). Every view is rendered by the single `Dashboard`
in `App.tsx`, so the simulation configuration and live stream stay mounted
across view changes.

| Header tab (`MainNav`) | Sub-nav                                                                                                                               | Routes                                                                                                                                   |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Compare                | step bar: Your junction → Watch both run → Results                                                                                    | `/app/comparative`                                                                                                                       |
| Saved                  | none                                                                                                                                  | `/app/history`, `/app/runs/:id`, `/app/compare?runs=`                                                                                    |
| Plan (sign-in)         | Planner · Experiment Copilot · Discovery Lab · Stress Lab · **API tokens**                                                            | `/app/planner`, `/app/copilot`, `/app/discovery`, `/app/stress`, `/app/tokens`, `/app/experiments/:id`                                   |
| Research lab (sign-in) | Overview · Your own junction · Three-way · Scenario planning · Validation · Traffic sweep · Signal on its own · Roundabout on its own | `/app/research`, `/app/junction`, `/app/three-way`, `/app/scenarios`, `/app/validation`, `/app/volume`, `/app/signal`, `/app/roundabout` |
| Admin (admins)         | none                                                                                                                                  | `/app/admin`                                                                                                                             |

Section membership lived in `shell/sections.ts`; labels and tab lists were
spread between it and `shell/Navigation.tsx`.

## 2. Most significant problems

1. **API tokens are buried in the experiment tools.** Reaching them meant
   opening Plan, then finding a fifth sub-tab among unrelated tools; the page
   called itself "Plan".
2. **Two things called "your junction".** The guided comparison's first step
   is "Your junction" while a different, batch study at `/app/junction` is
   "Your own junction" in the Research lab.
3. **Research lab is a flat list of eight tabs** mixing an explainer, method
   studies, a batch planning tool (Scenario planning) and two live
   single-control simulators, with no grouping.
4. **Planning is split.** Scenario planning (baseline vs intervention batch
   runs) sat in Research while the Planner and the other experiment tools sat
   in Plan; "Plan" also undersold Copilot, Discovery and Stress.
5. **Experiment pages had no place.** `/app/experiments/:id` highlighted the
   Planner tab even when the experiment came from the Copilot.
6. **Saved work is fragmented and undiscoverable.** Saved only lists saved
   runs. Planner studies, experiments, discovery searches, stress jobs and
   traffic sweeps each live inside their own tool, and Saved never says so.
7. **Inconsistent vocabulary.** "Save to History", "saved to History" and a
   section called "Saved"; eyebrows reading "Plan" on the token page.
8. **Dead ends after results.** The guided results offered other demand
   levels but nothing pointed to the deeper studies that answer "does this
   hold across traffic levels / on my real junction / formally?". A save
   toast confirmed the save but gave no way to open it.
9. **Experiment tools did not explain each other.** Nothing on the Copilot
   said when the Planner or Stress Lab is the better tool.

## 3. Proposed hierarchy (after)

One navigation model, defined once in `shell/sections.ts` (`SECTIONS`) and
rendered by `shell/Navigation.tsx`:

```
Header (persistent on every page)
├─ Primary workflows (segmented tabs)
│  ├─ Simulate          /app/comparative           step bar: Configure → Watch both run → Results
│  ├─ Research lab      /app/research              (sign-in)
│  │    Overview
│  │    Studies:        Custom junction study · Three-way study · Statistical validation · Traffic-level sweep
│  │    Single control: Signal on its own · Roundabout on its own
│  ├─ Experiments       /app/planner               (sign-in)
│  │    Planner · Scenario planning · Experiment Copilot · Discovery Lab · Stress Lab
│  │    (+ current experiment shown as a trailing crumb on /app/experiments/:id)
│  └─ Saved             /app/history               (+ run and compare pages)
└─ Utilities (right side)
   ├─ Developer         /app/tokens  (one click from anywhere; sign-in)
   ├─ Admin             /app/admin   (admins only)
   ├─ theme toggle, account
```

- Workflows sit in the centre; utilities sit on the right, so developer and
  admin pages never compete with the research and experiment groupings.
- Sub-nav groups carry labels on desktop and collapse to a scrollable row on
  phones. Every tab has a one-line description (tooltip and related-tools
  cards) taken from the same definition.
- Research and Experiment pages end with a "related tools" strip built from
  the same definitions, so moving between studies never needs the overview.
- No URLs change. Labels change only where they collided or misled.

## 4. Journeys

| Journey                                        | Before                                                                               | After                                                     |
| ---------------------------------------------- | ------------------------------------------------------------------------------------ | --------------------------------------------------------- |
| First visit                                    | Compare tab, step "Your junction"                                                    | Simulate tab, step "Configure" (same page)                |
| Run → save → find again                        | Results → "Save this comparison" → toast "saved to History" → click Saved → find row | Results → Save → toast with **Open saved run** link       |
| Results → deeper analysis                      | Back to header → Research lab → overview → pick tool                                 | "Take it further" links on the results page               |
| Study A → study B                              | sub-tab (flat 8)                                                                     | grouped sub-tab, or related-studies strip at the page end |
| Copilot → when to use Stress Lab?              | not stated                                                                           | related-tools strip describes each tool                   |
| Manage API tokens                              | Plan → sub-tab 5                                                                     | **Developer** in the header (one click, any page)         |
| Find a planner study / experiment / stress job | not signposted                                                                       | Saved → "Saved in other tools" says where each kind lives |

## 5. Risks

- **Routing / deep links:** none removed or renamed; `routing.ts`, the nginx
  template and the Vite fallback are unchanged.
- **Section moves:** `/app/scenarios` moves from Research lab to Experiments
  and `/app/tokens` from Plan to Developer. Both remain sign-in gated as
  before. Bookmarks still work.
- **Persistence:** unchanged. No new storage; Saved links to each tool's own
  list. Experiments still have no list endpoint, so Saved says they are
  reached from the tool that started them.
- **Tests:** label and landmark names used by tests changed (Compare →
  Simulate, Plan → Experiments, "Your own junction" → "Custom junction
  study"); tests updated alongside.
- **Not attempted:** a cross-page "simulation running" badge. The dual stream
  is torn down when leaving Simulate (`useWebSocketSnapshot` mode change), so
  such a badge would be wrong.

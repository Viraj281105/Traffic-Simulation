# Comparing control strategies (decision record)

Status: implemented on `viraj-dev`, uncommitted (2026-10-28).

## What changed

The guided comparison (Simulate, `/app/comparative`) used to run exactly two
engines: "a signal" (fixed-time or adaptive, by a setting) and "a roundabout"
(conventional or metered, by the scenario). It now runs any combination of
the registered strategies, each as its own first-class choice:

| Canonical id (backend registry) | Shown as | Controller |
| --- | --- | --- |
| `fixed_time_signal` | Fixed-time signal | `FixedTimeSignalController` |
| `adaptive_signal` | Adaptive signal | `AdaptiveSignalController` |
| `conventional_roundabout` | Roundabout | `RoundaboutController` |
| `metered_entry_roundabout` | Metered roundabout | `SignalisedRoundaboutController` |

## One source of truth

* **Which strategies exist** is the backend strategy registry
  (`backend/src/strategies`). `GET /api/strategies` publishes it with each
  strategy's family and whether the live comparison can run it.
* **Which the live comparison can run** is the derivation table in
  `backend/src/snapshot/strategy_comparison.py`: how each strategy's engine
  configuration is derived from the live scenario. Every derived
  configuration is checked against the registry (the controller factory must
  resolve it to the strategy it was built for), so a result can never be
  attributed to the wrong control.
* **How a strategy is presented** (short name, one-line explanation, colour,
  drawing) is `frontend/src/strategies/strategyCatalog.ts`. A strategy with no
  entry there still appears, with its registry name and description and a
  spare colour. Strategies the comparison cannot run are never offered.

Adding a fifth strategy is therefore: register it, add one derivation entry.
The picker, live grid, results, saving and reproduction need no change
(`strategyCatalog.test.tsx` covers a fifth strategy appearing as a card).

## Default selection

**Decision: all four strategies are always visible as cards; the default
selection is the fixed-time signal and the conventional roundabout.**
"All 4" and "Signal vs roundabout" shortcuts sit beside the count.

Why not all four by default:

* **Discoverability** comes from the cards, not from the default: every
  strategy is visible, named, explained and one tick away on the same screen.
* **Simplicity**: a first run reads as one clear comparison (two maps, two
  columns) rather than four of everything.
* **Cost**: each strategy is a full engine stepped in lockstep in real time;
  four doubles the server work of the familiar pair for every visitor.
* **Comparison quality**: the pair is the calibrated comparison the
  reliability check and earlier reports use; its plain-language explanations
  and charts apply to it directly.

Any combination from one to all four can be run. With none chosen, the run
button is disabled and the picker says why. The backend caps a comparison at
`maxStrategies` (currently four), and the picker disables further cards at
that limit.

## Live comparison

* `StrategyComparisonOrchestrator` runs the chosen strategies in lockstep on
  one seed and time step, sharing the lockstep loop with the original
  signal-vs-roundabout orchestrator (`snapshot/lockstep.py`). The dual
  orchestrator, its endpoints and the studies built on it are unchanged in
  behaviour.
* Endpoints: `/api/simulation/comparison/{play,pause,speed,reset,status}` and
  `/ws/simulation/comparison`. The choice travels in `/api/simulation/config`
  as `strategies`; an absent list means the default.
* A metered roundabout uses the scenario's entry-metering plan, or the
  default plan the scenario builder starts with (north–south then east–west,
  20 s greens, the registry's 3 s yellow and 2 s all-red).
* Warm-up, seeds, time step, metrics and their calculation are the engine's
  own and unchanged.

## Saved runs

A saved comparison is stored as run mode `comparison`, with
`summaryMetrics.strategies` keyed by strategy id and the strategy list in its
configuration (`comparison.strategies`), so reproduction re-runs exactly
those strategies. Saved runs in the old `dual` shape still open, list and
reproduce as before; when opened in Simulate, they map to the strategies they
actually ran.

## Known limits

* The signal-vs-roundabout charts and user-weighted scoring modal are offered
  only when exactly one signal and one roundabout are compared; their
  per-measure content for other combinations is in the new results page.
* The reliability check repeats the fixed-time signal against the roundabout,
  so it appears only when both are in the comparison.
* Scenario planning still offers its own three-strategy list (no metered
  roundabout); its batch path compiles scenario documents, which need an
  explicit metering plan.

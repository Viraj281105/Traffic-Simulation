# Cooperation screens: API contracts (package 3, V4.x)

The page `/app/cooperation` (`src/coopage/CooperationPage.tsx`; tabs Platoons,
Signal-free, Governance, Cost; the tab is in `?tab=`) is built against the
shapes below, copied from the backend code named in each row. Each feature
folder has `types.ts` (the source of truth), `api.ts`, `fixtures.ts` (contract
fixtures used by `src/test/cooperation.test.tsx`) and components. Shared
pieces are reused from `src/rescommon/` and `src/netcommon/`. Transport and
error envelope are as in `CONTRACTS_P6.md`.

All traffic results are in-model estimates. The hardware bridge tab was
skipped: `backend/src/hardware_bridge/` does not exist yet.

| Tab (folder)               | Request                                                   | Response type (file) | Backend source                       |
| -------------------------- | --------------------------------------------------------- | -------------------- | ------------------------------------ |
| Platoons (`platoon/`)      | `POST /api/v2/platoon/experiment`                         | `PlatoonExperiment`  | `platoon/router.py`, `experiment.py` |
| Signal-free (`aim/`)       | `POST /api/v2/aim/comparison`                             | `AimResult`          | `aim/router.py`, `experiment.py`     |
| Governance (`governance/`) | `GET /api/v2/governance/recommendations`                  | `RecommendationList` | `governance/router.py`               |
|                            | `POST /api/v2/governance/recommendations` (201)           | `Recommendation`     | `router.py`, `workflow.py`           |
|                            | `POST /api/v2/governance/recommendations/{id}/transition` | `Recommendation`     | `router.py`, `workflow.py`           |
|                            | `GET /api/v2/governance/audit`                            | `AuditLog`           | `router.py`, `audit.py`              |
|                            | `GET /api/v2/governance/audit/verify`                     | `AuditVerification`  | `router.py`, `audit.py`              |
| Cost (`costing/`)          | `POST /api/v2/costing/estimate`                           | `CostEstimate`       | `costing/router.py`, `estimator.py`  |
|                            | `GET /api/v2/costing/runs/{runId}?spot=`                  | `RunCost`            | `router.py`, `runcost.py`            |

Not used by a screen: `GET /api/v2/platoon/catalogue`, `GET /api/v2/aim/catalogue`,
`POST /api/v2/governance/shadow/report`, `GET /api/v2/costing/prices`,
`GET /api/v2/costing/tenants/{tenant}/summary`.

## Platoons (`platoon/`)

- Request: `{vehicles 2..20, durationSeconds 30..600, speedMps, timeGapSeconds, latencyMs 0..2000, lossProbability 0..1, brakeDecelMps2, seeds[2..10], method, confidence, channelSweep?{latenciesMs[1..3], lossProbabilities[1..3]}}`.
  The screen sends seeds `1..n`, `paired_t`, 0.95 and the sweep
  `[0, 200, 500]` ms by `[0, 0.2, 0.5]`. A request over the work limit is a
  422 with a reason.
- Response: `{seeds[], metrics{throughputVph|fuelLPer100Km|co2GPerKm: {platoonMean, humanMean, changePct|null, comparison (PairedComparison.to_dict), verdict}}, safety{platoonMinGapM, humanMinGapM, platoonCollisions, humanCollisions, platoonFallbackEvents}, perSeed[{seed, platoon{}, human{}}], isEstimate, label, channelSweep?[{latencySeconds, lossProbability, fuelChangePct|null, throughputChangePct|null, minGapM, collisions, fallbackEvents}], stringStability{vehicles, timeGapSeconds, controller, peakSpeedDeviationMps[], stepRatioMax, amplification, stable, minGapM, collisions}, throughputSteadyState{cacc, idm}}`.
- Platoon is arm A, human (IDM) arm B; `verdict` already accounts for which
  direction is better. The screen shows the `label` and says the numbers are
  in-model estimates.

## Signal-free (`aim/`)

- Request: `{durationSeconds 30..600, seeds[2..10], demandsVehPerHourPerApproach[1..6, each in (0, 900]], leftFraction, rightFraction, greenSeconds, yellowSeconds, allRedSeconds, messageLoss?{demandVehPerHourPerApproach, lossProbabilities[1..5]}, confidence, method}`.
  The screen sends demands `[150, 300, 450, 600]` and loss
  `[0, 0.25, 0.5, 0.8, 0.95]` at 450 veh/h.
- Response: `{provenance{seeds, durationSeconds, turnMix, signal, confidence, method, stressDemandVehPerHourPerApproach|null, assumptions[], inModelBestCase}, sweep[{demandVehPerHourPerApproach, aim, signal, comparison}], messageLossStress[{lossProbability, aim, signal, comparison}], gateGAim{passed, description}}`.
  `aim` and `signal` are `{meanDelay, stopsPerVehicle, throughputVph, p95Delay, lostMessages, safety{conflicts, minGapSeconds|null, deadlock, maxAccel, passed}}`;
  `comparison` has `meanDelay`, `stopsPerVehicle`, `throughputVph`, each a
  PairedComparison plus `verdict` (AIM minus signal).
- The screen always shows the in-model best-case warning and the G-AIM badge.

## Governance (`governance/`)

- `Recommendation`: `{id, scenarioRef, proposedChange{}, evidenceRefs[], createdBy, state ("draft"|"submitted"|"approved"|"rejected"|"withdrawn"), submittedBy|null, decidedBy|null, decisionComment|null}`.
- Create body: `{actor, id?, scenarioRef, proposedChange{}, evidenceRefs[]}`; 409 when the id exists.
- Transition body: `{actor, roles[], to, comment?}`. Errors: 404 unknown id, 403
  (approver role needed, the submitter cannot decide their own item, only the
  creator can submit or withdraw), 409 illegal transition, 422 a comment is
  required to reject. The screen shows the reason.
- `GET /audit` gives `{total, head, entries[{seq, timestamp (epoch seconds), actor, action, subject, payloadDigest, prevHash, hash}]}`;
  `GET /audit/verify` gives `{ok, length, head, error|null, badSeq|null}`.
- Advisory only: nothing here applies a recommendation to a live system.

## Cost (`costing/`)

- Estimate body: `{computeSeconds, vcpuWeight, instanceType?, spot, storedBytes, queueRequests, storageMonths}`.
  Response: `{items{compute, storage, queue}, total, currency, confidence ("estimate, not a bill"), assumptions[]}`.
- Run cost: the same fields plus `{runId, tenant, day|null, computeSeconds, costTags{}}`; 404 when no job record is stored.
- Every figure is labelled "estimate, not a bill".

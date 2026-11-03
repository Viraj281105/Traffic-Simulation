# Refactor findings

Findings from the repository-wide refactor (branch `viraj-dev`, base commit
`eb01213`; checkpoints 1-2 on 2026-10-29, 3-8 on 2026-10-29/30). Each names
the evidence it rests on. **Needs approval** means the change touches something beyond a
behaviour-preserving code edit (deleting a teammate's area or historical
assets, deployment secrets, a public API contract, a visual or product change)
and waits for the owner.

Status: **FIXED** (changed and verified) · **OPEN** (not started) ·
**NEEDS APPROVAL** (recommended, waiting for a decision).

## Summary

| ID | Area | Severity | Status | Needs approval |
| --- | --- | --- | --- | :-: |
| F-01 | Landing: per-frame forced layout and off-screen work | High (user CPU) | FIXED | |
| F-02 | Landing: ground layer re-traced every frame for still cameras | High (user CPU) | FIXED | |
| F-03 | `landingpage/` legacy Replit workspace (157 files) | Medium (maintenance) | DEFERRED (re-traced checkpoint 11): unreferenced and unbuildable; deletion waits for its author | yes (Khushi) |
| F-04 | 8 third-party reference PDFs (~44 MB) in `docs/resources/References/` | Medium (size, licensing) | DEFERRED (checkpoint 11): kept; per-file status in `docs/resources/README.md`; replace with citations before a public release | yes (licensing) |
| F-05 | 21 MB demo video in `recordings/` | Low (repo size) | RESOLVED (checkpoint 10): kept as the project's own deliverable; removal would not shrink history | |
| F-06 | nginx: static assets served without the security headers | Medium (security) | FIXED | |
| F-07 | CI frontend on Node 20 (EOL, below dependency engine ranges) | Low (CI drift) | FIXED | |
| F-08 | Landing still runs ~13 rAF loops and 7 intervals continuously | Low (residual CPU) | OPEN | |
| F-09 | `scripts/README.md` indexed 7 of 20 scripts | Low (docs) | FIXED | |
| F-10 | Root `src/__init__.py` import shim undocumented | Info | FIXED | |
| F-11 | File-by-file audit incomplete | Process | OPEN | |
| F-12 | Seven links to planning docs deleted in `d17cf2d` | Low (docs) | FIXED | |
| F-13 | No CI job built the bundle or checked its size | Low (regression detection) | FIXED | |
| F-14 | Compare section still ~36 % of the main thread at ~32 fps | Medium (user CPU) | RESOLVED (checkpoint 12): 30 fps cap on the compare tiles, measured -26 % main-thread time | |
| F-15 | Test, lint and type tools installed in the production backend image | Medium (image size, attack surface) | FIXED | |
| F-16 | Deploy workflow trusts any SSH host key (`ssh-keyscan`) | Medium (security) | FIXED with migration (checkpoint 10): pinned `EC2_KNOWN_HOSTS`, fail-closed; explicit logged opt-out | owner adds the secret |
| F-17 | `study_report.csv` tracked (two identical copies) although `.gitignore` excludes it | Low (hygiene) | FIXED (checkpoint 10): root copy removed; `docs/reports/` copy is canonical | |
| F-18 | Landing "Login" modal is a placeholder with fake notices | Medium (user trust) | FIXED (checkpoint 10): placeholder removed; Login opens the app's Cognito sign-in | |
| F-19 | Three GitHub project-management scripts read a deleted directory | Low (dead code) | FIXED (deleted) | |
| F-20 | Starlette deprecates `httpx` in its test client | Low (future break) | DEFERRED (checkpoint 10): dev-dependency change, schedule with the next test-tool upgrade | |
| F-21 | 403 responses carry error code `INTERNAL_ERROR` | Low (API clarity) | FIXED (checkpoint 10): `FORBIDDEN`; status unchanged; contract §6.2 | |
| F-22 | Cognito JWKS cache never refreshes after key rotation | Medium (reliability) | FIXED (checkpoint 8) | |
| F-23 | Token verification returned internal exception text | Low (information disclosure) | FIXED | |
| F-24 | `backend/.env` loader aborted silently on one malformed line | Low (reliability) | FIXED | |
| F-25 | Fallback pack checksums failed on any LF checkout | Medium (integrity claim) | FIXED | |
| F-26 | Tests leaked SQLite connections; one invalid escape sequence | Low (test hygiene) | FIXED | |
| F-27 | Cognito setup enabled password auth; rewrote `.env` dropping comments | Low (security, data loss) | FIXED | |
| F-28 | Frontend API client has no request timeout | Low (resilience) | FIXED (checkpoint 10): 60 s default, `ApiTimeoutError`; synchronous reproduce exempt | |
| F-29 | Documentation drift (shared, resources, compose, PR template, bootstrap) | Low (docs) | FIXED | |
| F-30 | Leader search is O(n²) per step | Low after measurement (≤ 6–18 % ceiling) | OPEN (deliberately not optimised) | |
| F-31 | Vitest 3 (test runner) has critical advisories; fix is Vitest 5 | Medium (dev tooling) | DEFERRED (checkpoint 10): production `npm audit` clean; a major test-tool upgrade on its own | |
| F-32 | `certifi` 2026.7.22 advisory PYSEC-2026-4320 | Medium (TLS trust store) | FIXED | |
| F-33 | `python-jose` / `ecdsa` advisories | Medium (unfixed advisories in the auth path) | FIXED (checkpoint 10): migrated to PyJWT 2.15.1; python-jose, ecdsa, rsa, pyasn1, six removed | |
| F-34 | Stochastic IDM leaked its per-call gap/headway scaling into the shared model | High (simulation correctness, unstructured traffic) | FIXED (behaviour change) | |
| F-35 | Engine reset split the spawner's and the stochastic IDM's random streams | Medium (reproducibility) | FIXED | |
| F-36 | Engine reset kept the deadlock detector's state and insight | Low (reporting) | FIXED | |
| F-37 | Collision audit cannot see overlaps between same-path or same-exit vehicles | Low (evidence blind spot) | RESOLVED (checkpoint 10): contract documented and guard-tested; runtime exempt-overlap metric deferred | |
| F-38 | `unstructuredTraffic` has no effect on driving when a vehicle mix is set | Medium (silent no-op; mislabelled runs) | FIXED stage 1 (checkpoint 5); stage 2 design open | |
| F-39 | Engine raises `KeyError` on a turn into a missing arm if validation is bypassed | Low (defence in depth) | FIXED (checkpoint 5): clear `ValueError` at `generate_route` | |
| F-40 | A zero-length signal phase (`allRedTime: 0`) is held for one tick | Low (signal timing) | FIXED (checkpoint 5); positive-duration plans unchanged | |
| F-41 | `averageDelay` counts only exited vehicles, so it understates delay under oversaturation | Medium (evidence interpretation) | FIXED (checkpoint 8): `unfinishedShare` reported; `averageDelay` unchanged | |
| F-42 | Conflict-zone tie-break compares vehicle ids as text (`veh_10` before `veh_9`) | Low (fairness wording) | RESOLVED (checkpoint 10): text order is the documented, pinned contract | |
| F-43 | `get_metrics()` rescans every exited vehicle on each call (once per snapshot) | Low-Medium (performance, long runs) | OPEN (measured, not changed) | |
| F-44 | TTC pair scan is quadratic and recomputes each vehicle's velocity per pair | Low (performance) | FIXED (checkpoint 7): per-vehicle precompute, events identical, scan 2.0-2.35x faster | |
| F-45 | Roundabout entry loop swallows any `KeyError` for a whole approach | Low (unsafe assumption) | FIXED (checkpoint 7): handler narrowed to the approach lookup | |
| F-46 | Comments describe `ConflictManager` as straight-chord; it samples real paths. Fuel-model comment arithmetic wrong | Low (docs) | FIXED (fuel comment checkpoint 6; five chord comments checkpoint 7) | |
| F-47 | Metric windows differ: PTI uses whole trips, collisions count from t = 0 | Low (evidence interpretation) | Documented in the metrics reference; no metric changed | |
| F-48 | `SignalisedRoundaboutController.__getattr__` recurses if built without `__init__` (copy/pickle) | Info (latent) | Confirmed; not changed (no supported path copies or pickles controllers) | |
| F-49 | Strategy comparison could not derive every strategy from a compiled single-strategy scenario | Low (latent contract defect) | FIXED (checkpoint 7) | |
| F-50 | Excess demand at a blocked entry is never admitted and appears in no metric | Medium-High (evidence interpretation) | FIXED: reported (checkpoint 8); opt-in point queue (checkpoint 9); selectable in the UI, labelled in studies and comparisons (checkpoint 10); `suspend` stays the default | |
| F-51 | A comparison frame could show its runs at different ticks | Low-Medium (snapshot integrity) | FIXED (checkpoint 7) | |
| F-52 | Study delay comparisons could credit a strategy for the traffic it did not serve | Medium-High (evidence interpretation) | FIXED (checkpoint 8): `servedDemand` on every paired comparison; planning flag and finding | |
| F-53 | Metric catalog and capacity card called admitted vehicles "offered demand" / "generated" | Medium (user-facing claim false under saturation) | FIXED (checkpoint 8) | |
| F-54 | Stress-lab breakpoints prefer the lowest-delay strategy even when it served less | Medium (evidence interpretation) | FIXED (checkpoint 9): `preferredServedLess` per level, shown in the UI | |
| F-55 | Study tables showed delay readings without the served-demand caution | Medium (evidence interpretation) | FIXED (checkpoint 9) | |
| F-56 | JWKS keys withdrawn by the pool stayed trusted until an unknown kid arrived | Medium (security) | FIXED (checkpoint 9): 1 h maximum cache age | |
| F-57 | Point-queue arrival clock restarted at each tick: fewer arrivals than configured (≈1 % at 900 veh/h per arm, ≈11 % at the maximum rate), entry waits timed from tick ends | Medium (opt-in model's demand) | FIXED (checkpoint 10): exact clock; `suspend` keeps its documented restart | |
| F-58 | Cold start during a Cognito outage: every request waited behind its own 10 s JWKS fetch under the lock | Low-Medium (availability) | FIXED (checkpoint 10): 15 s failure backoff, still fail-closed | |
| F-59 | Token issuer (`iss`) not checked | Low (defence in depth; keys are pool-specific) | FIXED (checkpoint 10): `iss` required and must be this pool | |
| F-60 | Entry model not selectable in the UI and not carried by the dashboard payload, the live sync or the three-way study; unlike entry models compared silently | Medium (integration) | FIXED (checkpoint 10) | |
| F-61 | Discovery Lab and the Stress generator could not run the queue entry model; a stress label ignored `advanced` overrides | Medium (integration) | FIXED (checkpoint 11) | |
| F-62 | find_leader's Layer 4 scanned every vehicle for every vehicle (about half the engine time at saturation) | Medium (performance) | FIXED (checkpoint 11): live spatial index, exact; 1.33-1.78x on busy runs | |
| F-63 | Predictive layer re-scanned routes for every vehicle pair | Low (performance) | FIXED (checkpoint 11): per-call route lane-id sets, exact; about 6 % | |
| F-64 | No structured logs, request ids or metrics | Medium (operability) | ADDED (checkpoint 12): JSON logs with redaction, request ids, protected /metrics | |
| F-65 | Copilot evaluation set ran as four aggregate assertions only | Medium (AI quality gate) | ADDED (checkpoint 12): explicit deterministic gate in CI; live mode opt-in | |
| F-66 | /api/v3 client had no request timeout | Low (resilience) | FIXED (checkpoint 12): 120 s | |
| F-67 | Live WebSocket could clobber its own replacement; retry left armed | Low-Medium (live view stability) | FIXED (checkpoint 12) | |
| F-68 | Study polling leaked an abort listener per poll | Low (memory) | FIXED (checkpoint 12) | |

## Details

### F-01 — Landing: per-frame forced layout and off-screen work (FIXED)

The cinematic landing page (`3568a39`) moved the hero camera in a
`requestAnimationFrame` loop that called `getBoundingClientRect()` every frame,
forcing a synchronous layout, whether or not the hero was on screen; the live
readouts re-rendered 3–4 times a second each, also off screen. `Hero.tsx` now
measures the section on resize and derives progress from `window.scrollY`, and
skips work off screen; `useHud`, the tile counters and the scrubber pause off
screen. Verified: landing tests, pixel identity, interleaved A/B
([PERFORMANCE_BASELINE.md](PERFORMANCE_BASELINE.md) §3: hero idle −40 %,
forced layouts 8.8 → 2.5 per second).

### F-02 — Landing: ground layer re-traced every frame (FIXED)

`drawScene` re-traced ~110 ground paths per frame per canvas although they
depend only on camera, size, theme and layout; boxes wholly off canvas were
still filled. `render.ts` now caches the ground once a view repeats (moving
cameras never allocate one) and skips boxes and shadows whose projected
corners all lie beyond one edge. Verified: 0 differing pixels on all seven
canvases against `HEAD` (`scripts/landing_canvas_diff.mjs`); unit tests for
the cache and the culling in `frontend/src/test/landing.test.tsx`.

### F-03 — `landingpage/` legacy workspace (NEEDS APPROVAL)

157 files from a Replit/pnpm export (added by Khushi in `c1f5813`/`9535791`).
Not built, deployed or imported anywhere (`git grep`: only
`docs/architecture/01` and `.dockerignore` mention it); excluded from the
backend Docker context. It cannot build as committed: its sources import
`./lib/logger`, `@workspace/api-zod` and `@/lib/utils`, but the root
`.gitignore` pattern `lib/` kept every `lib/` directory out of git. 110 files
are two copies of the generated shadcn/ui component set (differing only in
formatting). Its landing page shows invented figures ("Average delay 8.4 s", a
random "live flow" counter). Recommendation: delete the directory (git history
keeps it); the decision is the owner's and Khushi's.

### F-04 — Third-party PDFs (NEEDS APPROVAL)

Eight published documents (HCM material, the FHWA signal timing manual,
Treiber et al. 2000 and others; ~44 MB, largest 25 MB). Nothing reads them;
redistribution rights unchecked. `docs/resources/README.md` now lists them
with that caveat. Recommendation: replace with a bibliography of links.
Removing them from history would need a rewrite and is out of scope.

### F-05 — Demo video (NEEDS APPROVAL)

`recordings/urbanflow-final-demo.mp4`, 21 MB, unreferenced. Recommendation:
publish as a release asset and link it.

### F-06 — nginx security headers on static assets (FIXED)

The static-asset `location` declared its own `add_header`, so nginx inherited
none of the server-level ones: JS, CSS and SVG went out without `nosniff`,
CSP, frame and referrer headers. The block now repeats them; the CSP is held
in one `$csp` variable so the policy is still written once. Verified with the
production image `nginxinc/nginx-unprivileged:1.31.6-alpine` and the template:
before, `/assets/a.js` returned only the two `Cache-Control` headers; after,
all four security headers, while `/`, `/app/planner` and the proxied `/health`
were unchanged (200 with headers).

### F-07 — CI Node version (FIXED)

CI ran the frontend on Node 20 (end of life) while `frontend/Dockerfile`
builds on 26; under Node 20 several installed packages were outside their
declared engines (ESLint 10 `^20.19 || ^22.13 || >=24`, `@napi-rs/lzma`
`^22.20 || ^24.12 || >=25`). CI now uses Node 26. Verified: type-check, build
and the full test suite under Node 26.10 in the dev container (see the
completion audit); README and the bootstrap doc now say Node 24+.

### F-08 — Remaining continuous landing work (OPEN)

Clocks and canvas loops still request a frame each frame (returning early off
screen); interval timers still fire (their work is skipped). A shared ticker
driving only on-screen canvases would remove the rest; small measured gain.

### F-13 — Bundle-size check in CI (FIXED)

`frontend-lint-test` now runs `npm run build` and
`node ../scripts/check_bundle_budgets.mjs --dist dist` (budgets in
[PERFORMANCE_BUDGETS.md](PERFORMANCE_BUDGETS.md)). Needs its first CI run to
confirm on GitHub.

### F-14 — Compare section CPU (NEEDS APPROVAL, visual)

After F-01/F-02 the Compare section measures ~360 ms/s idle at ~32 fps; the
cost is raster work for ≈50 buildings and ≈40 vehicles per tile. Checkpoint 2
tried the one remaining cheap lever, drawing only each box's two nearest side
faces (the code's own comment says only those are visible): it changed 1.2–4 %
of pixels by up to 81/255 on every canvas, so it was reverted. Every remaining
option changes the picture (30 fps cap, lower pixel ratio, buildings in the
cached layer, pausing tiles not hovered) and needs a design decision.

### F-15 — Dev tools in the production backend image (FIXED)

`backend/requirements.txt` pinned pytest, pytest-cov, mypy, ruff and their
dependencies, so the API image shipped them. They moved to
`backend/requirements-dev.txt` (`-r requirements.txt` plus the tools and
pytest-xdist), which CI and local setup now install. Verified: production
image 420 MB → 274 MB; `pip check` clean; `src.main` imports; `/health`
answers; no pytest/mypy/ruff in the image; `pip install --dry-run -r
requirements-dev.txt` resolves.

### F-16 — Unpinned SSH host key in deploy (NEEDS APPROVAL)

`deploy.yml` runs `ssh-keyscan` and trusts whatever key the host presents, so
a network attacker at deploy time could impersonate the instance and receive
the deployment. Fix: store the instance's host key as a secret
(`EC2_KNOWN_HOSTS`) and write it to `known_hosts`. Needs the owner to add the
secret.

### F-17 — `study_report.csv` (NEEDS APPROVAL)

Generated output of `run_full_study.py`, tracked although `.gitignore` lists
it; no code reads it. Recommendation: `git rm --cached` it.

### F-18 — Landing "Login" modal (NEEDS APPROVAL, product)

`frontend/index.html` + `public/auth-modal.js`: submitting alerts "Form
submitted for: <email>"; "Forgot password?" says "Password reset instructions
sent!" and the social buttons show "… Login Triggered" — nothing is sent. Real
sign-in is Cognito in the dashboard. Recommendation: make "Login" open
`/app/comparative` (which signs in) and remove the placeholder form.

### F-19 — Obsolete GitHub scripts (FIXED, deleted)

`scripts/setup_github.py` and `assign_issues.py` built the V1 issues from
`docs/issues/`, deleted in `d17cf2d`; `set_milestone_deadlines.py` set
August 2026 V1 milestones on a hard-coded old repository. No references
outside the scripts README and one architecture line (both updated).

### F-20 — Starlette test client deprecation (OPEN)

Every TestClient run warns that `httpx` with `starlette.testclient` is
deprecated in favour of `httpx2`. Adding `httpx2` to
`requirements-dev.txt` is a dependency change to schedule with the next
upgrade.

### F-21 — 403 code in the error envelope (NEEDS APPROVAL, contract)

`STATUS_ERROR_CODES` has no 403, so scope and admin refusals carry
`INTERNAL_ERROR`; `docs/architecture/08` documents `INTERNAL_ERROR` as the
fallback, so this is contract behaviour. Recommendation: add
`403: "FORBIDDEN"` with a contract note.

### F-22 — JWKS cache never refreshes (OPEN)

`get_jwks()` caches the pool's keys for the life of the process. After a
Cognito key rotation every new token is refused until a restart. Fix: on an
unknown `kid`, refetch once, at most every few minutes (a cooldown keeps
random `kid`s from becoming a fetch amplifier).

### F-23 — Internal exception text in 401s (FIXED)

`verify_cognito_jwt` answered unexpected failures with
`Authentication error: {exception}` (for example `'exp'` for a token without
an expiry, or a JWKS fetch error). It now answers `Invalid token`, still 401,
and logs the cause. Test:
`test_a_refusal_carries_no_internal_exception_text`.

### F-24 — `.env` loader (FIXED)

`src/api/auth.py` loaded `backend/.env` inside `try/except: pass`; one line
without `=` raised and silently dropped every later setting. Extracted to
`_load_env_file`, which skips such lines; behaviour for valid files is
unchanged. Tests: `tests/api/test_env_file_loading.py`.

### F-25 — Fallback pack checksums (FIXED)

`fallback-pack/SHA256SUMS` hashed the CRLF files that a Windows build wrote,
while git stores LF, so 9 of 10 entries failed on any LF checkout. Every old
hash was first proven to match the committed content (9 as CRLF, 1 as LF); the
sums were then regenerated with CRLF normalised to LF, the convention
`d43e877` set for `v3_demo.py`. `build_fallback_pack.py` and
`w2_baseline_study.py` now write LF and hash normalised; the builder has a
`--verify` mode. Test: `backend/tests/planning/test_fallback_pack.py`.

### F-26 — Test hygiene (FIXED)

Nine `with sqlite3.connect(...) as conn:` blocks in four test files committed
but never closed their connections (12 `ResourceWarning`s in the baseline run);
they now use `closing(...)`. A Windows path in
`test_manifest_sidecar_hardening.py` used an invalid `"\w"` escape (a future
`SyntaxError`); it is now a raw string with the same value.

### F-27 — Cognito provisioning script (FIXED)

`scripts/setup_cognito.py` enabled `ALLOW_USER_PASSWORD_AUTH` although the
frontend signs in with SRP, and rewrote `.env` files keeping only `KEY=VALUE`
lines (comments and blank lines lost). It now enables SRP and refresh only and
edits keys in place (checked on a temporary file).

### F-28 — No request timeout in the frontend API client (OPEN)

`frontend/src/services/api.ts` calls `fetch` without an `AbortSignal`; a hung
backend leaves the UI waiting indefinitely. Add a timeout per call class.

### F-29 — Documentation drift (FIXED)

`shared/README.md` omitted two v3 schemas; `docs/resources/README.md` indexed
6 of 22 files; `docker-compose.yml` named a non-existent `frontend/nginx.conf`
and an outdated auth header; the PR template named a non-existent
`npm run format:check`; the bootstrap doc said Node 18+. All corrected.

### F-30 — Leader search (OPEN, deliberately not optimised)

**Evidence (checkpoint 3).** `vehicles/router.find_leader` has one call
site, `VehiclePool.update`, which processes `active_vehicles` in order and,
for each vehicle: may start its lane change, calls `find_leader`, then moves it
(`update_state`). So every lookup sees the earlier vehicles already moved and
the later ones not yet. Inside one call nothing mutates a vehicle (Layer 3's
reservation update touches only the conflict manager, which roundabouts do not
use). Two layers are O(n) per call: the roundabout branch of Layer 1 (every
active vehicle, per look-ahead ring lane) and the Layer 4 proximity scan
(every active vehicle, every geometry). Results are chosen with strict `<`, so
iteration order decides ties. `Vehicle.coords` is already memoised per
(lane, position).

**Exactness conditions for any speed-up.** Keep the iteration order and the
float arithmetic; skip only vehicles that provably cannot change the result
(Layer 4 has a bounded reach per pair; Layer 1's ring branch has none short of
the ring); and keep any index current after each vehicle's lane change and
move within the step, because a per-step snapshot would be stale.

**Ceiling.** An idealised filter with no maintenance cost (ring vehicles plus
everything within 25 m) took the saturated two-ring mixed run from 65–75 to
60–61 ms per simulated second (two runs each, 120 s): at most 6–18 %, within
run-to-run noise at the low end. A real incremental index would recover less
and adds a correctness risk to the most sensitive code in the engine.

**Decision.** Not optimised. New guard for any future attempt:
`tests/vehicles/test_leader_trace_pins.py` pins a digest of every
`find_leader` decision (vehicle, leader, gap to 1 µm) in three representative
runs (saturated two-ring roundabout with mixed vehicles, busy two-lane signal
with mixed vehicles, one-ring cars), identical on Windows/Python 3.14 and
Linux/Python 3.11. Checked to detect a filter that drops vehicles beyond 15 m
(all three digests change); reversing the iteration order changed nothing,
since exact ties do not occur in these runs.

### F-34 — Stochastic IDM parameter drift (FIXED, behaviour change)

`vehicles/stochastic_idm.py` scales the IDM's `_minimum_gap` and
`_desired_time_headway` for one call, by a random aggression draw, and
restores them at the end. The "nudge forward" and "hesitation" branches
returned before the restore, so each one left the scaling in place and the
next call compounded it into the single model every vehicle shares. Measured
in a 120 s run (`tests/engine/test_engine_reset.py` config with
`unstructuredTraffic`): the minimum gap went 2.0 → 1.125 → 0.34 → 1.16 →
0.2 m and the headway 1.5 → 0.84 → 0.51 → 1.73 → 0.3 s at 30-second
intervals: a random walk instead of variation around the configured values.
The intent is explicit in the code (`temp_min_gap` … `# Restore gaps`). Fix:
the restore is in a `finally`; the sequence of random draws is unchanged, so
only the leaked state differs. Runs with `unstructuredTraffic` change (that is
the fix); structured runs are untouched (the leader-trace pins and the golden
roundabout fingerprints pass). Regression test:
`test_stochastic_idm_parameters_do_not_drift` (fails on `HEAD`'s IDM:
1.08 m / 1.62 s after the loop).

### F-35 — Reset split the random streams (FIXED)

With `unstructuredTraffic` the engine builds the stochastic IDM with the
spawner's generator, so arrivals and driver noise draw from one stream.
`VehicleSpawner.reset()` replaced `self.rng` with a new `random.Random`, so
after `SimulationEngine.reset()` (the comparison's "Reset", described as a
fresh run of the same strategies) the IDM kept the old, advanced generator:
the rerun diverged from a fresh run (17 vs 26 vehicles at 30 s). Fix: re-seed
in place (`self.rng.seed(seed)`, the same state `random.Random(seed)` starts
in). Regression test:
`test_run_after_reset_reproduces_the_original_run_with_stochastic_drivers`.

### F-36 — Reset kept the deadlock detector (FIXED)

`DeadlockDetector` had no reset and `SimulationEngine.reset()` did not clear
it: after a reset, snapshots still reported the previous run's
`deadlockInsight` ("Natural deadlock emerged at 79.2s …") and 37 stopped times
keyed by vehicle ids the new run reuses. Added `DeadlockDetector.reset()`,
called from the engine reset. Regression test:
`test_reset_clears_the_deadlock_detector`.

### F-37 — Collision audit blind spot (OPEN, design question)

`VehiclePool._collision_audit` skips pairs on the same lane, on parallel
lanes of one street, or sharing any route lane (unless one is changing lane),
so a rear-end overlap between vehicles on one path (a car-following failure)
is never counted. Measured: 0 such overlaps (SAT on bounding boxes, onsets)
in the three leader-trace runs, so nothing is hidden there; but the reported
"0 collisions" cannot detect that failure mode. Recommendation: report
same-path overlaps as a separate count rather than changing the collision
metric's meaning; needs an owner decision because it adds a reported figure.

### F-31 — Vitest advisories (OPEN)

`npm audit --omit=dev` reports 0 vulnerabilities: nothing shipped to users is
affected. `npm audit` reports 4 in the test runner (Vitest 3.x via
`@vitest/mocker` path traversal and `tinypool` prototype-pollution RCE; 2
critical). They matter when a Vitest server is exposed, which CI and local runs
do not do. The fix is a major upgrade to Vitest 5 (and
`@vitest/coverage-v8`), a breaking change to schedule on its own.

### F-32 — certifi (FIXED)

`pip-audit -r backend/requirements.txt` flagged `certifi==2026.7.22`
(PYSEC-2026-4320, fixed in 2026.10.18). Pinned `certifi==2026.10.19`
(released ten days earlier; the CA bundle only). Re-audit clean for certifi;
API tests pass (539).

### F-33 — python-jose and ecdsa (OPEN, PO acceptance pending)

Still reported: `python-jose` 3.5.0 (no fixed release) and `ecdsa` 0.19.2.
The V2.0 completion audit (`docs/roadmap/V2_COMPLETION_AUDIT.md` R3.12)
recorded both as "PASS with accepted risk (PO to accept)": `ecdsa`'s issue concerns signing, which the backend never does,
and the token path pins RS256 (tested). Replacing python-jose (for example by
PyJWT) is the lasting fix.

### F-37 — checkpoint 5: what the collision metric measures

`VehiclePool._collision_audit` runs after every tick: for each pair of active
vehicles not exempted (same lane, parallel lanes of one street, or a shared
route lane, unless one is changing lane) and within 0.6 × (sum of lengths), it
tests the two oriented bounding boxes for overlap (separating-axis test). A
pair that starts to overlap adds 1 to `collisionCount` (debounced while the
overlap persists), and **the slower vehicle is stopped** (speed and
acceleration set to 0): the audit is not purely an observer. So the metric is
"onsets of geometric overlap between vehicles on different paths", with a
side effect on the run. The same-path exemption is intentional (comment:
close following is normal), but it also exempts real rear-end overlaps. The
proposal below stands; it should not stop vehicles, so it cannot change any
run.

### F-37 — proposal: a separately named same-path overlap count

Keep `collisionCount` exactly as it is. If the owner wants the blind spot
closed, add **`samePathOverlapCount`**: the number of distinct vehicle pairs
that start to overlap (oriented bounding boxes, the audit's own SAT test)
while the audit exempts them (same lane, parallel lanes of one street, or a
shared route lane, neither changing lane), counted once per onset as
`collisionCount` is. Reported next to `collisionCount`, never added to it.
Test plan: (1) two vehicles placed overlapping on one lane → count 1, collision
count 0; (2) the same pair overlapping for many ticks → still 1; (3) the three
leader-trace runs → 0 (measured in checkpoint 3); (4) metric contract docs and
the snapshot schema updated in the same change.

### F-38 — `unstructuredTraffic` ignored under a vehicle mix (stage 1 FIXED in checkpoint 5)

**Checkpoint 5, stage 1.** The product owner confirmed the intent: the flag
means chaotic, unpredictable but physically plausible driving. Every vehicle
class now drives `StochasticIDM` around its own profile, sharing the spawner's
random stream (`stochastic_idm_for`, wired in `SimulationEngine.__init__`).
Verified: mixed stochastic runs now differ from structured ones (fingerprint
`db9a30b2` → `4d47b215`); cars-only stochastic (`53556bad`) and mixed
structured (`db9a30b2`) runs are unchanged; golden fingerprints and
leader-trace pins pass; 8 runs (signal and 2-ring roundabout, 4 seeds,
900 veh/h, 120 s) had 0 collisions, no non-finite state, speed ≥ 0,
acceleration within class a_max + 0.5 and ≥ −9.5 m/s² (the model's reaction
jitter). Tests: `tests/vehicles/test_unstructured_mixed_traffic.py` and a
mixed stochastic case in `test_reset_matches_fresh_run.py`.
**Stage 2 (proposed, not built):** the existing model redraws "aggression"
every call (per vehicle per tick); a coherent model would draw a persistent
driving style per vehicle at spawn (headway, gap, acceleration, roundabout
critical gap within class-bounded ranges) and keep event-based hesitation.
That changes cars-only stochastic results, so it needs approval.

**Original diagnosis:**

The stochastic IDM is the engine-wide model; `VehiclePool.update` uses it only
for vehicles without a class profile (`vehicle_idm = params.idm` otherwise).
With any `vehicleMix` every vehicle has a profile, so the flag changes nothing
about driving; it only switches on the deadlock detector. Reproduced
(checkpoint 4): the same seeded fixed-time scenario with and without
`unstructuredTraffic` gives identical trajectories with a mix, different ones
with cars only. The guided setup offers both a mix and the unstructured
choice, so such runs are labelled unstructured but are not. A fix needs a
decision on what stochastic driving means per class (one shared random stream
for every class's IDM, per-class noise levels, motorcycles only?). Proposed
test: with a mix, `unstructuredTraffic` must change trajectories, and a reset
stochastic run must still equal a fresh one (the new
`test_reset_matches_fresh_run.py` covers the cars-only case today).

### F-39 — Turn into a missing arm (FIXED in checkpoint 5, defence in depth)

`RoadNetwork.generate_route` now checks the exit arm first and raises
`ValueError("No straight route from the east arm: this junction has no west
arm. validate_scenario rejects …")` instead of a `KeyError` from the
connection-lane builder. No caller caught the `KeyError`. The trust boundary
stays `validate_scenario`; the engine does not re-validate documents. Also
checked: in every validated three-arm layout (signal and roundabout, each
missing slot, 1-2 lanes; 3-4 lanes are rejected without explicit lane use),
0 of 72 lanes permit a turn into the missing arm, so the missed-turn re-route
in `lane_change._miss_turn` cannot reach it either. Test:
`test_a_turn_into_the_missing_arm_fails_with_a_clear_error`.

**Original finding:**

A three-arm scenario whose turning shares send traffic into the missing slot
passes `parse_scenario` and `compile_scenario`; the engine then raises
`KeyError: No outgoing approach for direction WEST` on the first such vehicle.
`validate_scenario` rejects the document with a clear message, and every API
path that compiles scenarios validates first (simulations, planning,
experiments, discovery, calibration, stress), so users cannot reach it.
Recommendation: have `generate_route` (or the spawner) raise a `ValueError`
naming the arm and turn, for scripts that skip validation.

### F-40 — Zero-length signal phase (FIXED in checkpoint 5)

Confirmed for both signal controllers (one tick per zero-length all-red:
fixed-time 2, adaptive 3 in 110 s). Reachable: scenario documents accept
`allRedTime` from 0 (`ge=0`); the dashboard's own input starts at 1 s. The
entry-metering plan already omits zero-length phases (`if all_red > 0`), which
sets the precedent. Fix: `FixedTimeSignalController.update` ends every phase
whose time is used up in the same tick (bounded by the plan length);
`AdaptiveSignalController.update` does the same for clearance phases, stopping
at a green. A phase of at least one tick ends exactly as before (one pass), so
positive-duration plans are bit-identical (leader-trace signal pin and full
suite unchanged). Measured after the fix: zero all-red 0 ticks, yellow hands
straight to the next green, 2 s all-red = 20 ticks, 0 collisions. Tests:
`tests/controllers/test_zero_duration_phases.py` (zero and positive all-red,
both controllers, order, exact phase durations over the cycle).

**Original finding:**

`FixedTimeSignalController.update` advances at most one phase per tick, so a
phase of duration 0 (the schema allows `allRedTime: 0`) is shown for one tick:
measured, each `all_red` phase took 1 tick (0.1 s), adding 0.4 s to every
four-direction cycle and showing an all-red that was not configured. Fix:
advance in a loop while the remaining time exceeds the phase's duration (or
drop zero-length phases when building the plan), with a test that
`allRedTime: 0` spends 0 ticks in all-red. Changes signal timing for such
configurations, so it waits for approval.

### F-41 — checkpoint 5: metric populations and proposal

Populations, verified in `metrics/collector.py` (`get_metrics`):

| Metric | Population | Denominator |
| --- | --- | --- |
| `averageDelay`, median, min, max, p95, SD | Vehicles exited at or after warm-up end | Their count |
| Delay of one vehicle | (exit − max(spawn, warm-up)) − free-flow time (route length ÷ desired speed, scaled for vehicles spawned before warm-up end), ≥ 0 | — |
| `throughput` | Same exited population | Count (not a rate) |
| `averageWaitTime`, `averageStopsPerVehicle` | Same exited population; pre-warm-up wait and stops subtracted | Their count |
| Queue average / max | Every post-warm-up tick, all approaches, all vehicles below the wait speed | Ticks (× approaches for the average) |
| `totalVehiclesSpawned` (post-warm-up) | Active + exited vehicles spawned at or after warm-up end | — |

Frontend: `metrics/catalog.ts` already says "vehicles that exited after
warm-up", so it is accurate about the population; the oversaturation caveat
is in `docs/research/metrics-reference.md` (checkpoint 4). The SD uses the
mean rounded to 0.01 s (error below 3·10⁻⁵ s²; left as is).

**Proposal (needs approval; new reported fields, existing ones unchanged):**

- `vehiclesInNetworkAtEnd` — active vehicles at the reading, all of them.
- `meanTimeInSystem` — over vehicles spawned at or after warm-up end, exited
  or not: (exit or reading time) − spawn. Unfinished trips are censored at the
  reading time, so it is a **lower bound** on their trip time; reported with
  `unfinishedShare`.
- `averageDelayIncludingActive` — exited delays as today plus, for active
  vehicles spawned at or after warm-up end, (reading time − spawn) − free-flow
  time for the distance covered so far, ≥ 0. Also a lower bound; never mixed
  into `averageDelay` and never shown as a completed-trip figure.

Test plan: hand-built pools with known spawn/exit times (exited only, active
only, both); warm-up boundary cases; a saturated run where the new lower
bound exceeds `averageDelay`; contract docs and snapshot schema in the same
change.

### F-41 — Delay counts only exited vehicles (OPEN, design question)

`averageDelay` (and the other delay order statistics) average post-warm-up
**exited** vehicles; vehicles still in the network at the end are excluded.
Measured (2-ring roundabout, mixed vehicles, seed 3, 240 s): at 500 veh/h per
arm, 57 vehicles were still inside (51 s in the network so far, against a mean
exited trip of 57 s, mostly in transit); at 1,000 veh/h, 119 were inside
(98 s so far, already longer than the exited trips' 86 s, still queued)
against 85 exited, so the reported 63.2 s understates the delay of the run.
The metric's definition is unchanged; its row in
`docs/research/metrics-reference.md` now states the limitation. Option for the
owner: report `vehiclesInNetworkAtEnd` and a separately named lower bound
including them (time in network so far minus free-flow time for the distance
covered).

### F-37 — checkpoint 6: the exemption is wider than same-path following

The audit skips a pair when the two routes share **any** lane. Every route is
incoming lane → connection lane → exit lane, so two vehicles from different
approaches bound for the same exit lane (a signal left-turner and the
crossing through movement it merges with; two roundabout vehicles leaving by
one exit) are never audited, on their approaches, in the box or on the ring,
not only once they follow each other. Collision handling itself: after each
pool update, every non-exempt pair within 0.6 × (sum of lengths) is tested
with the oriented-box SAT; an onset adds 1 to `collisionCount` and the slower
vehicle's speed and acceleration are set to 0 on that tick (so the
collector's stop count sees a stop). The contact stays one event until the
pair leaves the contact radius.

**Measured (observer only, nothing changed):** every exempt pair, by reason
(same lane, same street group, shared route lane), SAT-tested at every tick
of 12 runs of 240 s (two-ring roundabout 1,000 veh/h per arm mixed, one-ring
roundabout 700 veh/h cars, two-lane signal 900 veh/h mixed, three-lane
adaptive 900 veh/h mixed; seeds 1-3): **0 overlap onsets of any kind, 0
collisions.** So nothing is hidden in those runs; the blind spot is in what
the metric can show, not in what happened.

**Added:** `tests/engine/test_no_hidden_overlaps.py` checks every pair, exempt
or not, at every tick of two busy 60 s runs (the leader-trace scenarios),
about 6 s. Shown to fail when same-lane leaders are dropped from
`find_leader` (overlaps at 14.9 s and 22.5 s). The metrics reference now
states the exemption. **Proposal unchanged in spirit, widened in scope:** if
the owner wants it reported, `exemptOverlapCount` (onsets among audit-exempt
pairs, same SAT and debounce, never stopping a vehicle, never added to
`collisionCount`), optionally split into following and same-exit. Needs
approval: it is a new reported field.

### F-41 — checkpoint 6: candidate metrics evaluated

Every metric's population, from reading `collector.py` and all of
`metrics/definitions/` in full:

| Metric | Population | Window |
| --- | --- | --- |
| delay family, `throughput`, `averageWaitTime`, `averageStopsPerVehicle`, `totalStops`, `directionalFairnessIndex` | exited, exit at or after warm-up end | clipped at warm-up end (delay by time, wait and stops by baseline) |
| `travelTimeReliability` | same exited population | **whole trip** (exit − spawn), not clipped (F-47) |
| `vehicleTypeBreakdown`, `approachBreakdown` | exited (as delay) plus a count of active vehicles | as delay |
| `throughputRate` | exits in the last 60 s after warm-up | rolling |
| queue measures, `idleOpportunityLoss`, `intersectionUtilization`, `congestionRecoveryTime`, `speedVarianceIndex`, fuel/CO2, TTC, near-miss, PET, `signalTiming` | ticks after warm-up (fuel/CO2 and TTC over all active vehicles, including those spawned before) | per tick |
| `averageTravelSpeed`, `activeVehicleCount`, `currentQueueLengths` | active at the reading | instantaneous |
| `collisionCount`, `totalVehiclesSpawned` | whole run | from t = 0 |
| `criticalSaturationVolume` | throughput ÷ vehicles spawned after warm-up | — |

The three proposed lower bounds, computed beside the existing metrics on five
600 s runs (seed 1):

| Run | `averageDelay` | delay incl. active (lower bound) | unfinished share | mean time in system (lower bound) |
| --- | ---: | ---: | ---: | ---: |
| signal, 2 lanes, 300 veh/h per arm | 18.6 s | 18.3 s | 4.8 % | 40.2 s |
| signal, 2 lanes, 900 veh/h, mixed | 143.4 s | 146.7 s | 32.9 % | 164.2 s |
| adaptive, 2 lanes, 900 veh/h | 88.6 s | 88.5 s | 20.2 % | 108.1 s |
| roundabout, 1 ring, 400 veh/h | 64.9 s | 64.2 s | 19.2 % | 85.1 s |
| roundabout, 2 rings, 1,000 veh/h, mixed | 142.2 s | 147.4 s | 33.5 % | 166.2 s |

**Reading.** The censored delay lower bound moves `averageDelay` by −0.7 to
+5.2 s even with a third of the post-warm-up vehicles unfinished: vehicles
still inside include many that arrived recently, whose delay so far is small,
so it adds little and invites being read as a better delay. The unfinished
share is the informative number (5 % → 34 %), cheap and unambiguous.
**Recommendation:** if the owner wants a change, add only
`vehiclesInNetworkAtEnd` and `unfinishedShare` (vehicles spawned after
warm-up still active ÷ all vehicles spawned after warm-up) first; keep the
time-in-system lower bound as a research output, not a headline. Test plan as
before (hand-built pools; warm-up boundary; a saturated run; contract docs and
snapshot schema in the same change).

### F-42 — Conflict-zone tie-break orders vehicle ids as text (OPEN)

`ConflictManager._judge_zone` breaks a tie between equal-priority movements
with `other_id < vehicle_id`; ids are `veh_{n}` without padding, so `veh_10`
sorts before `veh_9`. The module docstring says "lower ID wins", meaning
the earlier vehicle. The order is still total and deterministic (exactly one
of a pair yields), so no deadlock and no reproducibility issue: only which of
two simultaneous equal-priority arrivals goes first differs, at each change in
digit count. The predictive layer's last-resort tie (rule 7) and the PET
occupant pick use the same text order, both documented there as arbitrary.
**Recommendation:** correct the docstring (no behaviour change), or compare
spawn order, which changes signal-run results and the golden pins and so
needs approval.

### F-43 — `get_metrics()` cost grows with exited vehicles (OPEN, measured)

The queue history was made incremental earlier for this reason, but the
delay, wait, PTI, fairness, per-class and per-approach figures still loop
over every exited vehicle (summing each route's lane lengths) on every call,
and `SnapshotBuilder.build` calls it once per snapshot (every tick for
buffered runs). Measured on a fixed-time run, replicating its exited list:
4.1 ms at 1,000 exited vehicles, 10.4 ms at 2,000, 23.1 ms at 4,000 (about
6 µs per exited vehicle, machine under load), against a step of about 14 ms.
Linear, so about 50 ms at 8,000 exited vehicles (an hour, the schema's
longest run, at 2,000 veh/h in total): inside the 100 ms real-time budget,
so left unchanged. **If needed:** accumulate each exited vehicle's delay,
clipped wait/stops and travel time once at exit (all are fixed by then), keep
sorting for the order statistics, and add a test that compares the full
metrics dictionary with the rescanning computation on a long run.

### F-44 — TTC pair scan (OPEN, measured)

`find_ttc_events` tests every pair of active vehicles within 50 m on
different lanes, every post-warm-up tick: 11 % (two-ring roundabout) and 15 %
(two-lane signal) of total step time in busy 180 s runs (cProfile), almost
all in `compute_ttc` for pairs that pass the radius test, which recomputes
both vehicles' velocity vectors (two `sin`/`cos`) per pair. Precomputing
position, velocity and radius once per vehicle per tick gives identical
results (the formula is symmetric and nothing depends on event order); a grid
would not help much, since most pairs near the junction are within 50 m.
Measurement-only code, so no correctness risk; left for a performance pass.

### F-45 — Roundabout entry loop swallows `KeyError` (OPEN)

`RoundaboutController.update` wraps each approach's whole entry evaluation in
`try: ... except KeyError: pass`, meant for a missing approach. Any other
`KeyError` raised inside (gap acceptance, merging entries, the entry gate)
would silently skip that approach for the tick, leaving last tick's give-way
obstacles in place. The file's own comment records that this exact pattern
once hid a real bug (lane ids keyed by single letters). Traced in checkpoint
6: no `KeyError` can currently arise inside the block (the id lookups have
their own handler; the gate's dictionaries are pre-filled). **Recommendation:**
narrow the handler to the `get_incoming_approach` call, so a future error
fails loudly instead of yielding silently wrong runs. Not changed, since there
is no defect to demonstrate.

### F-46 — Documentation drift in the conflict layers (comment arithmetic FIXED)

`ConflictManager.compute_conflict_points` samples each connection lane's real
path (its docstring explains why the chord was dropped), but three places
still describe it as straight-chord: the comment at the top of
`VehiclePool.update`, the `predictive_conflicts` module docstring and the
`safety_conflicts` module docstring. The roundabout still runs without
`ConflictManager`, but the stated reason is out of date. Recommendation: one
docs pass stating the current reasons (ring following by `find_leader`, gap
acceptance by the controller). **Fixed:** `environmental_estimates.py` gave the
fuel model's cruise figure as "0.45 + 2.70 = 3.15 L/h" and the speed term
alone as "~12 L/100 km"; the constants give 2.16 + 2.70 = 4.86 L/h (8.1 L/100
km), of which the speed term is 4.5 L/100 km. Comments only; constants and
outputs unchanged.

### F-47 — Metric windows differ (documented)

`travelTimeReliability` uses whole trips (exit − spawn) while delay, wait and
stops are clipped at warm-up end, so a vehicle that spawned during warm-up
contributes its warm-up time to the PTI. `collisionCount` counts from t = 0
(already documented). Both are now stated in the metrics reference. Changing
either changes reported values, so neither was changed.

### F-48 — `__getattr__` delegation can recurse (latent)

`SignalisedRoundaboutController.__getattr__` returns
`getattr(self.roundabout, name)`. On an instance created without `__init__`
(`copy.copy`, `pickle`), `self.roundabout` is itself missing, so the lookup
recurses until `RecursionError`. Nothing copies or pickles controllers today
(`deepcopy` is used only on configs). If that changes, guard with
`if name == "roundabout": raise AttributeError(name)`.

### F-17 — checkpoint 6

There are two tracked, byte-identical copies: `study_report.csv` and
`docs/reports/study_report.csv` (the second indexed in `docs/README.md` as a
record). `docs/product/urbanflow-evaluation-metrics.md` already notes their
content is an all-zero sweep with a retired hard-coded recommendation that a
test now forbids the code from producing. Recommendation unchanged: remove the
root copy; remove or relabel the docs copy as historical. Owner decision.

### F-31 — checkpoint 6

Re-audited 2026-10-30: unchanged. `npm audit`: 4 (2 critical, 2 moderate),
all through Vitest 3.2.7; fix is Vitest 5.0.5 (major).
`npm audit --omit=dev`: 0.

### F-44 — checkpoint 7: TTC scan (FIXED, exact)

**Established first.** `find_ttc_events` has one caller, `MetricCollector.update`,
a tick callback that runs after the pool update; nothing moves a vehicle during
the scan, so a velocity computed once per call cannot go stale. The candidate
set (pairs on different lanes within `ttcSearchRadius`) and the formula are
unchanged. A spatial grid was not pursued: in busy runs most pairs near the
junction are inside the 50 m radius, so it would prune little (and F-30's
index question is a different code path).

**Change.** Each vehicle's coordinates, velocity vector and radius are
computed once per call; `compute_ttc` and the scan share one core function
(`_ttc`), so the formula exists once. **Equivalence:** against the `HEAD`
implementation loaded side by side, identical event lists (pairs, order,
values) at every tick of four runs (two-ring roundabout and two-lane signal,
mixed traffic, 60 s and 180 s; 118,675 events), and identical `minTTC`,
`ttcEventCount`, `ttcSampleCount` and `nearMissCount`. **Benchmark:** scan
0.45 → 0.19 ms per tick (60 s runs) and 1.56 → 0.76 / 1.48 → 0.72 ms per tick
(180 s runs), 2.0-2.35x. End to end, interleaved three runs each, step time
17.9 → 16.1 ms (roundabout median) and 15.1 → 14.9 ms (signal), inside this
machine's run-to-run noise. **Test:** `tests/metrics/test_ttc_scan_pins.py`
(scan equals per-pair `compute_ttc` at every tick, and a digest recorded with
the `HEAD` scan).

### F-45 — checkpoint 7 (FIXED)

The handler now guards only `get_incoming_approach(d)` (a slot with no arm,
V1.5) and `continue`s; the rest of the approach's evaluation is outside it.
An AST comparison with `HEAD` shows the loop body after the lookup and the
rest of the module unchanged. Test: `tests/controllers/test_roundabout_entry_errors.py`
(a `KeyError` from an entry gate now surfaces; on `HEAD` it was swallowed, the
test fails there with "DID NOT RAISE"; a three-arm roundabout still runs).
Golden fingerprints and leader-trace pins pass unchanged.

### F-46 — checkpoint 7 (FIXED)

Five comments no longer describe `ConflictManager` as chord-based:
`VehiclePool.update`, `predictive_conflicts` (module docstring),
`safety_conflicts` (PET docstring), `tick_callback`, and `find_leader`'s
Layer 4. They now state the current reason the roundabout runs without it
(ring following by `find_leader`, entry by gap acceptance, exits by the
controller's zones, other cross-ring conflicts by the predictive layer). The
three remaining mentions of the chord are explicitly historical.

### F-42 — checkpoint 7

Introduced with the first engine (`e3f8cd9`) as "lower ID wins"; ids were
never padded, and its one test (`v0_alpha` against `v1_beta`) uses ids whose
text and number order agree. So it is an incidental detail, not a stated
contract, but every signal run's results depend on it. Kept unchanged; the
docstring and comment now say "compared as text", and
`tests/intersection/test_conflict_tie_break_order.py` pins it (`veh_9` yields
to `veh_10`). **Recommended behaviour** if fairness by arrival is wanted:
compare spawn order (a numeric key); that changes signal fingerprints and
leader pins and needs approval and a re-record in the same diff.

### F-48 — checkpoint 7

Confirmed: `copy.copy`, `copy.deepcopy` and `pickle` of a
`SignalisedRoundaboutController` all raise `RecursionError`, as does any
attribute lookup on an instance made with `__new__`. No supported path does
any of these: configs are the only objects deep-copied, and the study's
process pool sends configs, not engines. Left unchanged, per the brief; the
guard (`if name == "roundabout": raise AttributeError(name)`) is the fix if
controllers are ever copied or sent to workers.

### F-49 — Comparison derivation broken by a declared strategy (FIXED)

`strategy_engine_config` derives a strategy's config from a source config and
checks the result resolves to that strategy. `extract_explicit_strategy`
honours a declared name (root or controller `strategy`, or
`scenario.strategy`) over the structure, and `compile_scenario` writes
`scenario.strategy`. So from a compiled fixed-time scenario the adaptive run
raised `StrategyCompatibilityError`, and from an adaptive one the fixed-time
run resolved to adaptive (reproduced). Not reachable from today's entry
points, whose configs come from `compile_live_comparison`
(`"fixed_time+roundabout"`, which resolution ignores) or recordings of them;
any other caller hit it. Fix: the derivation drops declared names from its
copy before deriving (nothing in the engine reads them), then verifies as
before. Current inputs derive the same configs less one metadata key. Test:
`tests/strategies/test_comparison_derivation.py` (4 strategies × 4 source
kinds; the caller's config is not modified).

### F-50 — Demand that cannot enter is dropped silently (documented)

`VehicleSpawner.step`: when an arrival finds every permitted entry lane full,
its approach's timer is set to 0 and the same arrival is retried each tick;
no further arrivals are generated on that approach until it is placed. There
is no queue outside the network, so the demand that arrives meanwhile is
lost, and none of it appears in any metric (`totalVehiclesSpawned` counts
admitted vehicles). Measured (seed 1, 600 s): two-lane signal at 300 veh/h
per arm, 104 % of the offered demand admitted (Poisson noise); two-lane signal
at 900 veh/h mixed, **53 %**; two-ring roundabout at 1,000 veh/h mixed,
**51 %**, with an arrival held on ~48 % of approach-seconds. With F-41 (a
third of the admitted still inside at the end), `averageDelay` in such runs
describes about a third of the offered demand. **Done:** the metrics reference
says so (`totalVehiclesSpawned` row). **Proposal (needs approval, with F-41):**
count arrivals per approach that were due but not admitted, and report
`deniedArrivals` (or offered vs admitted) next to `vehiclesInNetworkAtEnd`
and `unfinishedShare`; a point-queue model outside the network would change
results and is a separate decision.

### F-51 — Torn comparison frames (FIXED)

The lockstep loop steps the runs one after another under the orchestrator's
lock; `SnapshotBuilder.build` holds only its engine's lock; the dual and
strategy-comparison WebSocket streams build frames with
`asyncio.to_thread`. A frame built between two runs' steps showed them at
different ticks: reproduced deterministically with the frame claiming tick 6
while the roundabout run was at 5 (dual) and runs at 6, 5, 5 (comparison).
Fix: `get_dual_snapshot` and `get_snapshot` hold the orchestrator lock
(`LockstepOrchestrator.snapshot_lock()`), the same order the loop takes locks
in, so a frame waits at most one tick and no deadlock order is introduced.
Test: `tests/integration/test_comparison_snapshot_coherence.py` (fails with a
no-op lock as shown). Single-engine snapshots were already coherent (built
under the engine lock) and do not change simulation state: they read the
controller and collector and only fill memoised coordinates.

### F-37, F-41, F-43 — checkpoint 7

Unchanged. The overlap guard passes; no metric fields were added. F-41's
evaluation now has to be read with F-50: unfinished journeys and never-admitted
demand are separate populations, and a decision on reported fields should
cover both (`vehiclesInNetworkAtEnd`, `unfinishedShare`, denied arrivals).
F-43: no new evidence of a problem; left.

### F-50 — checkpoint 8: demand accounting (FIXED, behaviour unchanged)

**Traced.** `VehicleSpawner.step`: an arrival becomes due when its approach's
timer reaches 0; `_attempt_spawn` places it or returns None. On None the
timer is held at 0 and the turn and class drawn for it are kept, so the
**same** arrival is retried each tick; the next inter-arrival time is drawn
only after it is placed. So the approach's arrival process is *suspended*
while its entry is full: the demand is not dropped after being generated, it
is never generated. Nothing else removes vehicles: every admitted vehicle is
active or exited (`exited_vehicles` is never evicted), already checked each
tick by `run_invariant_checks`.

**Decision.** Account for the demand without changing the entry model:
counters in the spawner that draw nothing from its random stream and never
touch the timers. `demand_accounting()` reports, per approach and in total,
exact `arrivals`, `admitted`, `waitingAtEntry` and measured
`entryBlockedSeconds`, plus two expectations from the configured rate
(`nominalDemand`, `estimatedSuppressedArrivals` = rate × blocked time,
flagged by `demandFiguresAreEstimates`) and `admittedShareOfNominal`. Every
`get_metrics` caller passes it as `demandAccounting` (snapshot, readout,
registry, calibration, study runner and validation). Exact identities:
`arrivals = admitted + waitingAtEntry`, `admitted = active + exited`; the
study validation now checks the first every tick too.

**Not chosen (needs a decision):** a point queue outside the network (SUMO's
insertion backlog), which keeps the arrival clock running and admits
backlogged vehicles later. It is the more realistic model, but it raises the
admitted demand of every saturated run, so every saturated result and the
golden pins would change; it should be opt-in or a deliberate default change.

**Evidence.** Golden fingerprints: the trajectory pins are untouched; the
metrics and snapshot pins match the original recordings with the two new
keys left out of the hash (`ADDED_METRICS` in `roundabout_golden.py`), so
every pre-existing value is bit-identical. A traced run with and without
reading the accounting gives identical vehicles and an identical final RNG
state. `tests/vehicles/test_demand_accounting.py` (10 tests): identities at
every tick of light and saturated signal and saturated roundabout runs;
saturated runs report blocked time and suppressed demand, and
arrivals + suppressed is within 25 % of the nominal demand; light demand is
blocked only by close Poisson pairs (1.0 s in 300 s); reset clears; the
vehicle limit stops the nominal clock. Reset-equals-fresh now compares it.

**Measured** (two-lane signal scenario, 80/10/10 car/bus/truck, 600 s,
warm-up 60 s, seeds 1-5, mean admitted share of nominal demand):

| Demand per arm | Fixed-time | Adaptive | Roundabout |
| ---: | ---: | ---: | ---: |
| 300 veh/h | 1.02 | 1.02 | 1.02 |
| 600 veh/h | 0.73 | 0.72 | 0.81 |
| 900 veh/h | 0.51 | 0.50 | 0.55 |

### F-41 — checkpoint 8 (FIXED)

`unfinishedShare` (vehicles admitted at or after warm-up end still in the
network ÷ all admitted after warm-up; null until one is) is reported beside
the unchanged `averageDelay`. Not added: `vehiclesInNetworkAtEnd`, which is
`activeVehicleCount` read at the final tick; the censored delay lower bound
(checkpoint 6: moves the mean by -0.7 to +5.2 s, invites misreading). Same
study as above: unfinished share 0.21/0.21/0.11 at 300 veh/h, 0.34-0.37 at
600, 0.36-0.40 at 900.

### F-52 — Delay comparisons could credit traffic not served (FIXED)

`run_scenario_comparison` and `run_control_comparison` read every pair of
strategies by mean delay alone (`lower`/`higher`/`tie`/`inconclusive`), and
planning studies turn those into "better"/"worse" findings. Delay averages
only vehicles that finished, so a strategy that admitted less (F-50) or left
more unfinished (F-41) could read as better for that reason alone. **Fix,
additive:** `unfinishedShare` and `admittedShareOfNominal` are summarised per
strategy with the other measures, and every pair carries `servedDemand`
(differences, `comparable`, and `lowerDelayServedLess`: the lower-delay side
admitted less or left more unfinished by more than 5 points,
`study/tolerances.py`). A planning study lists such alternatives in
`validity.servedDemandDiffers` and adds a high-confidence reliability
finding. The delay `reading` is unchanged. The first version flagged any
population difference; the measured study showed that over-warns (at
300 veh/h the roundabout's 25 s lower delay came with a 10-point *lower*
unfinished share, i.e. it served more), so the flag is directional. Tests:
`tests/study/test_served_demand_caveat.py` (8, including a real comparison).
In the measured study no pair was flagged: at saturation the strategies'
admitted shares differ by at most 9 points, and the one with the lower delay
served as much or more.

### F-53 — "Offered demand" wording (FIXED)

`metrics/catalog.ts` described `totalVehiclesSpawned` as "the offered demand
unless generation hit the per-run vehicle limit", false under saturation
(51-55 % above). The label is now "Vehicles admitted" with a corrected
description; the live capacity card says "admitted" (not "generated") and, once
at least 20 arrivals were expected, "N % of configured demand". New catalog
row `unfinishedShare` ("Unfinished after warm-up"). Frontend types, snapshot
schema, metric contract §7.10a and the metrics reference describe the new
fields. Seen live on the Docker dev stack (bind-mounted working tree): the
signal's metrics panel shows "Unfinished after warm-up 70.0 %" and
"Vehicles admitted 30 veh" at 1:46 of a default run.

### F-22 — checkpoint 8 (FIXED)

A token whose `kid` is not in the cached key set now triggers one refetch
(`_refresh_jwks_for_unknown_kid`), only when the cached set is older than
`JWKS_REFRESH_COOLDOWN_SECONDS` (300 s); the attempt restarts the cooldown,
so made-up `kid`s or a failing endpoint cause at most one fetch per 5 min. A
failed refetch keeps the keys already held (logged, not raised). Fetches run
under a lock, so concurrent first requests fetch once. The verification path
is otherwise unchanged. Test: `tests/api/test_jwks_rotation.py` (4: cached
once; rotated key accepted after the cooldown; 40 unknown-kid tokens cause
one refetch; failed refetch keeps old keys). Three of the four fail with the
refresh disabled. Residual: a rotation is picked up up to 5 min late for a
token signed with the new key if a refetch happened in the previous 5 min.

### F-50 — checkpoint 9: entry models compared, opt-in point queue

**Exact current semantics (default, "suspend").** An *arrival* is generated
when an approach's arrival timer expires (Poisson or uniform inter-arrival
times drawn from the spawner's stream). It is *offered* to the entry at once;
if no permitted entry lane has clearance it is *held*: its turn and class
are kept, it is retried every tick, and the approach's timer stays at 0, so
no further arrival is generated there until it enters. Held arrivals are
never lost, replaced or duplicated (one per approach, `arrivals = admitted +
waitingAtEntry` every tick). Under persistent congestion the approach's
arrival process is throttled to the entry's discharge, so the demand that
would have arrived is never generated; it is visible only as the expectation
`estimatedSuppressedArrivals`.

**Alternatives evaluated.**

| | A. Suspend (default) | B. Point queue outside the network (opt-in) | C. Physical upstream storage (longer approaches) |
| --- | --- | --- | --- |
| Physical reading | Upstream traffic diverts or never departs; nothing is stored | Vertical queue (SUMO insertion backlog, Aimsun virtual queue): vehicles wait at the network edge, occupying no road | Real road upstream: queues have length, block, interact |
| Existing scenarios | Unchanged | Unchanged unless enabled | A different scenario; already possible (approach length up to 1,000 m) |
| Reproducibility | Seeded | Seeded; a different random sequence from A (turn and class drawn on arrival) | Seeded |
| Conservation | Exact for generated arrivals; offered demand only as an expectation | Exact: arrivals = admitted + waiting + rejected; arrivals track the nominal demand | As A once the longer road also fills |
| Memory and time | Constant | Queue bounded by `totalVehicles` (at most 5,000 tuples) and optionally a per-approach `capacity`; per-tick cost unchanged within noise | Grows with the vehicles simulated on the longer roads |
| Golden pins | Unchanged | Unchanged (default path bit-identical) | Unchanged (a different scenario) |
| Strategy fairness | Hides entry waits: a strategy that blocks entries more is not charged for it | Charges the wait (`averageEntryWait`) and shows each strategy's backlog | Charges it as in-network delay, until the longer road spills back too |

**Measured** (two-lane fixed-time signal and two-ring roundabout scenarios,
80/10/10 car/bus/truck, 600 s, warm-up 60 s, seeds 1-5; means):

| Control, veh/h per arm | Model | Arrivals | Admitted | Waiting at end | Mean entry wait | Delay | Throughput | Unfinished |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Fixed-time, 300 | A | 204 | 204 | 0 | 0.1 s | 56.0 s | 161 | 0.21 |
| Fixed-time, 300 | B | 207 | 205 | 2 | 0.2 s | 59.2 s | 158 | 0.22 |
| Fixed-time, 600 | A | 295 | 292 | 2 | 1.9 s | 124.0 s | 193 | 0.36 |
| Fixed-time, 600 | B | 414 | 313 | 101 | 42.7 s | 136.2 s | 194 | 0.40 |
| Fixed-time, 900 | A | 309 | 307 | 2 | 3.8 s | 159.1 s | 196 | 0.40 |
| Fixed-time, 900 | B | 598 | 311 | 287 | 80.1 s | 153.8 s | 201 | 0.39 |
| Roundabout, 600 | A | 327 | 325 | 2 | 1.3 s | 119.0 s | 209 | 0.37 |
| Roundabout, 600 | B | 414 | 338 | 75 | 19.6 s | 126.3 s | 216 | 0.37 |
| Roundabout, 900 | A | 330 | 328 | 2 | 3.2 s | 162.4 s | 211 | 0.40 |
| Roundabout, 900 | B | 605 | 339 | 266 | 62.7 s | 157.1 s | 214 | 0.40 |

Reading: in-network figures move little (admitted +2-7 %, about one to two
seed standard deviations; delay, throughput and unfinished share within
noise), because the entry's discharge, not the arrival timing, limits
admission. What B adds is the demand A never generates and the time it
waits: at 900 veh/h per arm about half the offered demand is still waiting
outside at the end, and admitted vehicles waited 63-80 s before entering.
That can change a comparison: by in-network delay the fixed-time signal is
marginally lower at 900 veh/h (A: 159 vs 162 s), but delay from arrival under
B is lower for the roundabout (157 + 63 = 220 s against 154 + 80 = 234 s).
Per-tick cost: 15.7-16 s (A) against 16-17 s (B) per 500 ticks at about 100
vehicles in the network, on a loaded machine; `demand_accounting()` takes
42-50 µs against about 950 µs for the `get_metrics()` read it accompanies.

Option C measured (fixed-time, 900 veh/h per arm, approaches 450 m instead
of 150 m, model A, seeds 1-3): 541 admitted (90 % of the nominal demand,
against 51 % on 150 m roads), mean entry wait 0.3 s, delay 169.4 s,
throughput 205, **unfinished share 0.70** with 335 vehicles still in the
network, and 99.6 ms per tick, about three times the 150 m runs (about
32 ms per tick on the same loaded machine). The longer road stores the
backlog as real queues, so it appears as unfinished in-network trips rather
than as waiting demand, at three times the run time, and it fills in turn
at higher demand or in longer runs. Different seed count from the table
above; read the comparison as indicative.

**Decision.** B is the most defensible model for saturated studies and is
implemented as an opt-in (`traffic.entryQueue` in engine configs and scenario
documents; a per-approach `capacity` beyond which arrivals are rejected and
counted; `totalVehicles` caps arrivals and `vehicleLimitReached` follows
them). A stays the default: every existing scenario, golden pin and saved
result reproduces, and changing the default would move every saturated
result. C is not a separate model: longer approaches already provide it, and
it only moves the boundary. **Owner decision:** whether new studies, or the
saturated levels of the study presets, should default to B.

**Invariants and tests.** `tests/vehicles/test_entry_queue.py` (12):
conservation every tick for signal, roundabout and capacity 3; arrivals
within 10 % of the nominal demand and nothing suppressed; capacity respected
and rejections counted; `enabled: false` bit-identical to no option
(trajectory hex, RNG state, accounting); FIFO per approach; the vehicle limit
caps arrivals and is reported; seeded reruns and reset reproduce;
fingerprints change only when enabled; `averageEntryWait` equals the exited
vehicles' mean. `tests/integration/test_entry_queue_end_to_end.py` (4): HTTP
compile and validation, the simulations endpoint keeps the option in the
stored config, snapshots validate against the snapshot schema and list no
waiting vehicle, and a study reports the queue per seed for every strategy.
Golden pins unchanged, with `averageEntryWait` added to `ADDED_METRICS`.

### F-54 — Stress breakpoints preferred a strategy that served less (FIXED)

`stress/lab.run_breakpoints` picks, per level, the strategy with the lowest
mean delay. Each level row now also reports every strategy's mean delay,
admitted share and unfinished share, and `preferredServedLess` (the shared
`lower_delay_served_less` rule against every other strategy). The preference
and breakpoints are unchanged; the Stress Lab table shows "served less of the
demand; may explain its lower delay" on flagged levels. Tests:
`tests/experiments/test_stress_served_demand.py` (3) and
`frontend/src/test/stressServedDemand.test.tsx`.

### F-55 — Study tables without the caution (FIXED)

The scenario study and the three-way study now show the same caution under a
delay reading whose `servedDemand.lowerDelayServedLess` is set
(`frontend/src/metrics/servedDemand.ts`), worded as "may explain part of the
difference", never as better or worse. Results saved before the field
existed show nothing. Tests: `servedDemand.test.ts`, and the three-way study
render test asserts the caution on exactly the flagged pair.

### F-56 — Withdrawn JWKS keys stayed trusted (FIXED)

After F-22 the cached key set was refreshed only when a token named an
unknown kid, so a key the pool withdrew kept verifying for the life of the
process. `get_jwks` now refetches once the set is older than
`JWKS_MAX_AGE_SECONDS` (1 h). Reviewed: unknown kids trigger at most one
fetch per 5 min cooldown, also under concurrency (16 threads, one fetch); a
failed refetch keeps the previously published set (fail-open on
availability, never on signature: every token still needs a valid RS256
signature from a published key, and forged tokens are refused while the pool
is down); the 10 s request timeout runs under the lock, so concurrent
requests wait for one fetch instead of each fetching. Tests: three added to
`tests/api/test_jwks_rotation.py`; the two max-age tests fail against the
cache-forever `get_jwks`.

### F-33 — checkpoint 9: reachability

OSV, 2026-10-30: python-jose 3.5.0 has GHSA-3qf3-8w2g-rqmx (CVE-2024-33663,
HMAC/asymmetric algorithm confusion via DER public keys; no fixed release);
ecdsa 0.19.2 has GHSA-wj6h-64fc-37mp (CVE-2024-23342, Minerva timing attack
on ECDSA signing; no fix); cryptography 50.0.1 and rsa 4.9.1 have none.
Neither path is reachable: `verify_cognito_jwt` refuses any header `alg`
other than RS256 before constructing a key, keys come from JWK dicts with
`algorithm="RS256"` forced, and the backend never signs with ECDSA.
`test_algorithm_confusion_and_unsigned_tokens_are_refused` forges HS256
with the public key as the secret, and `alg: none`; both are refused. No
dependency changed. Lasting fix (owner's call): replace python-jose with
PyJWT, which removes python-jose, ecdsa, rsa and pyasn1 from the image.

### Application integration — checkpoint 9 trace of the new fields

Generation (spawner) → collection (`get_metrics`; all six callers pass the
accounting) → snapshot (schema-validated) → `/api/v1/simulations` and the
live WebSocket snapshots → persistence (history stores the whole metrics
dict and the engine config, so reproductions keep `entryQueue`; runs saved
earlier lack the new fields and the frontend types make them optional) →
studies (`_MEASURES` summarise `unfinishedShare`, `admittedShareOfNominal`
and `averageEntryWait`; per-seed rows carry `demandAccounting`) → planning
(validity flag and finding) → stress lab (F-54) → discovery (reviewed,
unchanged: throughput is a maximised objective beside delay) → stress
failure classes (reviewed, unchanged) → frontend (types, catalog rows
"Unfinished after warm-up" and "Wait to enter", capacity card, study
cautions; the metrics CSV export is catalog-driven, so it includes the new
scalar rows) → SDK and CLI (no metric models; they pass dicts through).
Not exposed yet: discovery candidate metrics and stress failure classes do
not carry the new fields, and no UI control sets `entryQueue` (scenario
documents, the API and the SDK do).

### Checkpoint 10 — demand-model integration, auth migration, decision register

**F-60 — the entry model, end to end (FIXED).** Checkpoint 9's trace ended
with "no UI control sets `entryQueue`". Traced again field by field:

| Layer | Before | Now |
| --- | --- | --- |
| Engine config, scenario documents, validation | `traffic.entryQueue` (checkpoint 9) | unchanged |
| Dashboard payload (`live/dashboard_config.py`) | key ignored | `entryQueue` compiled when enabled; malformed values are a 400; absent/disabled keeps the config byte-identical |
| Frontend config (`types/config.ts`) and live sync (`useLiveConfigSync`) | no field; the sync rebuilds the payload field by field, so a new field would have been dropped silently | `entryQueue` carried, normalised (disabled = absent) |
| Guided setup, junction builder | no control | `EntryModelChoice` ("When traffic cannot get in"): hold back (default) or queue outside, optional per-road limit, a glossary of waiting / admitted / exited / still in network / rejected |
| Three-way study | no way to choose | request `entryQueue` (built-in junction; with a scenario it belongs in the document); result `entryModel` |
| Scenario study, planning | via the document | result `entryModel`; the result page names a queue run |
| Paired comparisons | `servedDemand` | plus `averageEntryWaitDifference`, `entryWaitReversesDelay` |
| Study tables | delay only | "Wait to enter" column only for queue results; caution when the wait reverses the delay order |
| Live capacity card | admitted / exited / in network | plus "N waiting outside, M rejected" under the queue model |
| Stored-run comparison | silent | API `entryModels` + `warnings`; saved-run page caution |
| Experiment packages | — | `experiment.json` carries the scenario's `traffic.entryQueue`; the fingerprint differs (tested) |
| Discovery, stress generator, copilot proposals | build fresh documents | always the default model, consistently within a run (limitation, not a drop) |

Tests: `backend/tests/integration/test_entry_model_propagation.py` (25),
`frontend/src/test/entryModel.test.tsx` (17).

**F-57 — the point queue's arrival clock (FIXED, opt-in model only).**
`_step_queued` reset an approach's timer to a fresh inter-arrival draw after
each arrival and generated at most one arrival per approach per tick, so
each gap was rounded up to a whole tick: a 4/7 s uniform gap became 0.6 s
(105 → 100 arrivals per approach in 60 s), and at 10 veh/s Poisson the run
generated about 11 % fewer arrivals than configured. Arrival times were
tick ends. Now the leftover is carried, every due arrival is generated, and
each records its due time. The model exists only in this uncommitted tree,
so no saved result changes. Three of the eleven tests in
`tests/vehicles/test_entry_invariants.py` fail on the old clock (checked by
reverting the block). The default `suspend` model has the same restart; it
is kept (every golden pin and saved result reproduces) and documented in
contract §7.10a with its size (≈0.3 % at the dashboard default, ≈1 % at 900
veh/h per arm, ≈11 % at the maximum).

**Entry models re-measured with the exact clock** (two lanes, 150 m
approaches, 80/10/10 car/bus/truck, 900 veh/h per arm, 600 s, warm-up 60 s,
seeds 1-3; means; model results, not field data):

| Model | Control | Arrivals (nominal 600) | Admitted | Waiting at end | Delay | Wait to enter | Delay from arrival | Throughput | Unfinished |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| suspend | Fixed-time | 314 | 312 | 2 | 156.5 s | 2.3 s | 158.8 s | 197 | 0.41 |
| suspend | Roundabout | 330 | 328 | 2 | 162.6 s | 2.0 s | 164.6 s | 211 | 0.40 |
| queue | Fixed-time | 639 | 301 | 339 | 172.5 s | 27.9 s | 200.5 s | 187 | 0.42 |
| queue | Roundabout | 626 | 338 | 288 | 163.5 s | 22.2 s | 185.7 s | 213 | 0.41 |

Paired delay, fixed-time minus roundabout: `suspend` −6.1 s (−18.0 to
+5.8), read as a tie; `queue` +9.1 s (+4.7 to +13.5), roundabout lower,
`comparable: false` (admitted shares 50 % vs 56 %), `lowerDelayServedLess:
false` (the roundabout served more), `entryWaitReversesDelay: false` (its
vehicles also waited less outside). So the entry model changes this study's
reading from "tie" to "roundabout lower". "Wait to enter" here is
`averageEntryWait`, over vehicles that exited after warm-up (the delay
population); vehicles still outside or still in the network at the end are
not in it. Run time 262 s (suspend) vs 285 s (queue) for 6 runs each on 8
workers.

Clock bias check: arrivals ÷ nominal over 20 seeds (saturated one-lane
signal, Poisson, 1 veh/s, 300 s) = 0.992 ± 0.017 (s.e.): unbiased. The
3-seed arrivals above (+4 to +6.5 %) are within that noise. The checkpoint 9
table (F-50) was measured with the old queue clock; its `queue` rows
understate arrivals by about 1 % at 900 veh/h per arm and are superseded by
this one for the 900 veh/h case.

**Invariants re-validated** (`test_entry_invariants.py`, 11; with the 26 of
checkpoint 9): conservation and no double counting (pool ids unique, waiting
vehicles never in the pool) at every tick; zero-length steps generate
nothing under either model; a completed run accounts for every arrival
(exited + still in + waiting + rejected); queue memory bounded by
`totalVehicles` at the maximum rate (each waiting arrival a three-field
record under 200 bytes; at most 5,000); reset mid-run reproduces a fresh run.
Exact counters versus estimates: `arrivals`, `admitted`, `waitingAtEntry`,
`rejected` and the entry waits are counted; `nominalDemand`,
`estimatedSuppressedArrivals` and hence `admittedShareOfNominal` are
expectations (`demandFiguresAreEstimates`).

**F-33 — PyJWT migration (FIXED).** OSV, 2026-10-30: python-jose 3.5.0
GHSA-3qf3-8w2g-rqmx / PYSEC-2026-4298 (no fix); ecdsa 0.19.2
GHSA-wj6h-64fc-37mp / PYSEC-2026-1325 (no fix); PyJWT 2.15.1, cryptography
50.0.1, rsa 4.9.1, pyasn1 0.6.4: none. Reachability was a property of
today's code, not of the dependency, and the migration surface was one
function, so it was done: `verify_cognito_jwt` now uses
`jwt.get_unverified_header`, `jwt.PyJWK` and `jwt.decode(algorithms=["RS256"],
issuer=…)` requiring `exp` and `iss`. Kept: the header `alg` check before the
key lookup, the JWKS cache and refresh rules, the audience rule (`aud` or
`client_id`), not checking `iat` (clock skew), the 401 texts. Changed: `iss`
is now required (F-59); a token at exactly its `exp` second is refused
(PyJWT `exp <= now`; it was accepted). Requirements: `PyJWT==2.15.1`
replaces `python-jose[cryptography]`; `ecdsa`, `rsa`, `pyasn1`, `six`
dropped (resolver: 48 packages, none of them). Tests: the forgeries (HS256
with the PEM and with the DER public key, `alg: none`, tampered payload,
wrong key, unknown kid) are all refused; issuer and refusal-reason tests
added; run with python-jose uninstalled from the venv.

**F-58 — JWKS cold-start outage (FIXED).** With no keys cached, every
request retried the fetch under the lock with a 10 s timeout, so requests
queued serially behind outbound calls. A failed initial fetch now pauses
retries for 15 s (tokens are refused either way: fail-closed). Test:
`test_a_cold_start_outage_backs_off_and_recovers`. Reviewed unchanged: 1 h
maximum age, unknown-kid refresh at most once per 5 min, single flight under
the lock, failed refresh keeps the published keys, RS256 only.

**F-28 — frontend request timeout (FIXED).** `services/api.ts` `request()`
aborts after 60 s with `ApiTimeoutError`; a caller's own abort signal still
cancels; the synchronous `reproduce` call passes `timeoutMs: null`. Long work
already runs as study jobs (202, then polled). Test: `apiTimeout.test.ts` (3).

**Decision register.**

| Item | Classification | Decision and evidence | Tests / docs | Residual risk |
| --- | --- | --- | --- | --- |
| F-03 `landingpage/` | Defer with justification | Re-checked: not built, deployed, imported or buildable (its `lib/` dirs were never committed); shows invented figures. The evidence supports retiring it, but it is another contributor's work, so deletion waits for Khushi. Options: (a) delete, history keeps it (recommended); (b) move to an archive branch; (c) keep with a "not built" README banner | — | Confusion only; nothing ships it |
| F-04 reference PDFs | Defer with justification | Legitimate research references; kept. Redistribution rights cannot be established from the repository. Options: (a) keep while the repository is private (status quo); (b) replace with a bibliography of links before any public release (recommended if it goes public) | `docs/resources/README.md` caveat | Licensing, if shared |
| F-05 demo video | Resolve now | The project's own deliverable; kept. Deleting it would not shrink clones without a history rewrite | — | Clone size |
| F-16 SSH host key | Resolve with migration | Contract: connect only to a pinned key (`EC2_KNOWN_HOSTS`) with `StrictHostKeyChecking yes`; a missing secret fails the deploy; `ALLOW_UNPINNED_EC2_HOST_KEY=true` is the only way to scan, and annotates the run with a warning | Six shell branches exercised locally; YAML parses; `docs/deployment/production-cicd-setup.md` | **The next deploy fails until the owner adds `EC2_KNOWN_HOSTS`** (or sets the opt-out) |
| F-17 `study_report.csv` | Resolve now | Byte-identical (same SHA-1). The `docs/reports/` copy is the one the docs index and the comparative report cite; the root copy is the script's default output path, already gitignored, read by nothing. Root copy deleted from the working tree | `comparative_report.md` | None |
| F-18 placeholder login | Resolve now | Exposed in production, not a dev placeholder: a password form that sent nothing and claimed "reset instructions sent". Removed (markup, script, about 250 lines of CSS); "Login" links to `/app/comparative?signin=1`, which opens the real Cognito dialog unless already signed in | `landing.test.tsx`, `signInLink.test.ts` (3) | None known |
| F-21 403 code | Resolve now | Clients branch on the status (the frontend never reads codes; the SDK maps classes by status). `INTERNAL_ERROR` on a 403 mislabels authorization as a server fault. Added `403: FORBIDDEN`; status unchanged; contract §6.2 (now also lists 413 and 422) | PAT and replay 403 tests assert the code; mapping test | A client matching `INTERNAL_ERROR` on a 403 (none found) |
| F-37 overlaps | Resolve now (contract) | `collisionCount` = onsets of oriented-box overlap among audited pairs; same-lane, same-street and shared-route-lane pairs are exempt unless one changes lane; the slower vehicle is stopped. Written in the metrics reference; `test_no_hidden_overlaps.py` checks every pair in CI. A runtime `exemptOverlapCount` is deferred: 0 onsets in 12 measured runs, and the guard catches the only mechanism that would create them | metrics reference, guard test | A new failure mode in untested scenarios would not be reported at run time |
| F-42 tie-break | Resolve now (contract) | Text order of ids kept: deterministic, total, pinned; spawn order would change signal results and golden pins for no measured fairness gain (ties need equal priority on one tick) | `test_conflict_tie_break_order.py`; module docstring | None |
| F-50 default model | Resolve now | `suspend` stays the default (every legacy scenario and pin reproduces); `queue` is now selectable in the UI and labelled wherever it changes the reading | as F-60 | Users must choose `queue` for saturated studies |
| F-14 compare CPU | Defer | Every remaining lever changes pixels; a design decision | — | Idle CPU |
| F-20 httpx2 | Defer | Dev-only dependency change; not upgraded indiscriminately | — | Future Starlette break |
| F-31 Vitest 5 | Defer | Production audit clean; a major test-tool upgrade on its own | — | Dev tooling only |
| F-38 stage 2 | Defer | Persistent driver styles are a modelling design question | — | — |
| F-43 `get_metrics` cost | Defer | Measured and bounded; no change without a benchmark showing need | — | Long runs |
| F-08, F-30, F-48 | Unchanged | As recorded | — | — |

**Remaining comparison limitations.** Within a study every strategy shares
one entry model by construction; across saved runs the API and the page now
warn. Seeds are not comparable across entry models (turn and class are drawn
on arrival). Discovery and the stress generator always use `suspend`. The
`suspend` model's tick-rounded clock lowers `admittedShareOfNominal`
slightly (documented, not changed). `429` still reads
`SIMULATION_LIMIT_REACHED` for every rate limit, including authentication
lockouts (noted, not changed: contract wording).

### Checkpoint 11 — entry model in the labs, engine performance, register

**Reconciliation.** HEAD `eb01213`, nothing staged or stashed, no test
processes. Since checkpoint 10 another actor changed seven paths (Oct 30
18:21-18:48): CSV formula-injection hardening (`src/csv_safety.py` used by
`simulations/router.py` and `planning/report.py`, with
`tests/api/test_csv_safety.py` and an allow-list entry in
`tests/planning/test_boundary_and_schema.py`) and a stress-breakpoint
`entryModel` label (`stress/lab.py`, `StressLabPage.tsx`, `services/v3/stress.ts`).
They were kept and built on, not redone; the label now reads the effective
model (below).

**F-61 — Discovery Lab and Stress generator could not run the queue (FIXED).**
Both built fresh scenario documents with no entry model and neither request
could carry one. Now:

| Path | Change |
| --- | --- |
| `discovery.models.Regime.entryQueue` | strict `EntryQueueSpec`; `regime_scenario` writes it beside the aggression profile; the unseen grid's `model_copy` keeps it. `SearchSpec.fingerprint` drops an absent or disabled queue, so every earlier specification keeps its fingerprint |
| Discovery objective | under the queue the delay objective is the delay from arrival (`averageDelay + averageEntryWait` per run), so no candidate gains by keeping traffic out; `inNetworkDelay` is reported beside it. Default model: in-network delay, unchanged |
| Discovery result | `entryModel`; held-out candidates and baselines carry `servedDemand` (entry wait, admitted share, unfinished share; reported, never optimised); each comparison with a baseline carries `lowerDelayServedLess` |
| `stress` suite | `SuiteRequest.entryQueue` applied on top of the deterministic generator (the generator's draws are untouched); per-strategy admitted and unfinished shares; `lowestDelayServedLess` per scenario; `entryModel`. Default suite fingerprints unchanged |
| `stress` breakpoints | `BreakpointRequest.entryQueue` for the default junction (rejected beside a scenario, which carries its own); `_at_level` keeps it at every level |
| Effective model | `scenario.documents.scenario_entry_model` / `config_entry_model` read the compiled config, so an `advanced.traffic.entryQueue` override is labelled as the engine runs it (the stress label read only `traffic.entryQueue`) |
| Experiments | result `provenance.entryModel`; package inspection `manifestSummary.entryModel` (from `experiment.json`). Outside the hashed evidence: result fingerprints unchanged |
| Frontend | entry-model control on the Discovery and Stress pages; result sentences; served-less cautions on Discovery comparisons and Stress suite rows |
| Contracts | v3 OpenAPI snapshot regenerated: three additive `entryQueue` fields and `EntryQueueSpec` |

Searched for other silent resets (every assignment that replaces a `traffic`
block): the copilot proposer builds fresh documents (default model,
consistent within a proposal; the experiment it proposes keeps any model the
user then sets); `advanced` merges deeply (nothing dropped); the live
dashboard, planning and study builders were covered in checkpoint 10. SDK
and CLI pass specifications through as dictionaries. Study and planning jobs
expose no cancel, so `run_simulation_tasks` ignoring the cancel flag is
consistent; the labs use the isolated runner, which honours it.

Tests: `backend/tests/integration/test_entry_model_labs.py` (15: the real
search and suite drivers with a recording executor, every compiled config
checked; one run of the real engine), `frontend/src/test/labEntryModel.test.tsx`
(4).

**F-62 — Layer 4 proximity scan was O(n²) (FIXED, exact).** Profiled a
saturated run (two lanes, 900 veh/h per arm, 80/10/10 mix, 300 s, in
process): `find_leader` was 102 s of 206 s, almost all Layer 4 scanning
every active vehicle for every vehicle (16 M `coords` reads). Layer 4 can
act only within `2.5 + 0.3 + (L_a + L_b + W_a + W_b) / 2` m, so
`vehicles/proximity.ProximityGrid` (cells at least that wide, 3 x 3
neighbourhood) returns every candidate, re-filed live after each vehicle
moves (the pool updates sequentially), in active-list order (identical tie
order). Proof: `tests/vehicles/test_proximity_index.py` checks every query
against a brute-force scan in three busy scenarios (signal, adaptive three
lanes, two-lane roundabout; >10,000 queries each); leader-trace pins (every
decision to 1 µm), golden trajectory fingerprints and reproducibility tests
unchanged. Interleaved A/B in one process, metrics identical in every pair
(medians of 3; the machine was loaded, with single outliers on both sides):

| Workload | Before | After | Ratio |
| --- | ---: | ---: | ---: |
| Saturated signal, 2 lanes, 900 veh/h/arm, 300 s | 52.7 s | 29.6 s | 1.78x |
| Two-lane roundabout, 800 veh/h/arm, 300 s | 46.7 s | 35.1 s | 1.33x |
| Light signal, 1 lane, 235 veh/h/arm, 300 s (5 pairs) | 8.82 s | 8.73 s | 1.01x (no change) |

**F-63 — route scans in the predictive layer (FIXED, exact).** After F-62 the
predictive layer was next (30 s of 114 s profiled): every pair re-scanned a
route for the other's lane. Each route's lane ids are now collected once per
`compute_braking_distances` call (routes do not change during it). A/B,
saturated signal, 3 pairs, metrics identical: 29.1 → 27.5 s (about 6 %).
Small, kept because it is exact and local.

Combined, the saturated signal run takes about half its former time. Study
runs parallelise across processes, so a busy study's wall time falls by about
as much. Not changed (measured, smaller or semantic): the collision audit
(6.6 s), TTC scan (7 s), roundabout Layer 1 arc scan, F-43 `get_metrics`.

**F-14 — landing comparison CPU.** Re-read `SimCanvas`: it already repaints
only on screen and only when the replay clock or camera moved; the remaining
cost is rasterising the scene while the replay advances. No further
visual-preserving change was identified from the code, and the in-browser
re-measurement could not be completed this session (the browser pane was
closed). Decision unchanged: the remaining levers (30 fps cap, lower pixel
ratio, buildings in the cached layer, pausing unhovered tiles) change the
picture and need a design choice. Recommendation if one is wanted: a 30 fps
cap on the four compare tiles only (halves their raster work; motion is
slower-sampled but the frames are the same scenes).

**F-03 — `landingpage/`.** Re-traced: referenced only by `.dockerignore`
(excluded) and the architecture doc (described as not built); no workflow,
compose file, nginx template, Vite config or import uses it; its `lib/`
directories were never committed, so it cannot build. Decision unchanged:
retiring it is supported by the evidence but it is Khushi's work; recommended
option (a) delete it (history keeps it).

**F-04 — reference PDFs.** Documentation references, not runtime assets or
deliverables (`docs/` is excluded from the images); the methodology cites
Treiber et al. 2000. `docs/resources/README.md` now lists each file, its use
and its redistribution status (all unverified; HCM/TRB and journal articles
very likely not redistributable). Kept; replace with citations before any
public release.

**Browser verification (partial).** Working-tree backend (port 8765, Python
3.14, commit `eb01213`) and Vite (port 5180) in the browser pane: the landing
page has the real "Login" link (`/app/comparative?signin=1`) and no password
field; it opens the dashboard (the dev session is signed in, so no dialog);
guided setup shows "When traffic cannot get in", selecting the queue reveals
the limit field and the population glossary, laid out as designed. Not
exercised in the browser: running a comparison, saved-run comparison,
Discovery and Stress pages, cancellation, responsive and dark layouts (the
pane was closed before those steps; they are covered by component tests).

### Checkpoint 12 — index validation, observability, Copilot gate, browser checks

**Reconciliation.** HEAD `eb01213`, nothing staged or stashed, no test
processes; 180 changed paths as recorded at checkpoint 11 and no file changed
after it.

**F-62 re-validated (proximity index).** New
`backend/tests/vehicles/test_proximity_reference.py` (15): at sampled ticks
of seven scenarios (light one-lane, saturated two-lane, adaptive three-lane,
cars only, one- and two-ring roundabouts, and the maximum per-arm demand the
schema accepts on three lanes), every vehicle's `find_leader` with the index
equals the exhaustive full scan: the same vehicle object, or a virtual
obstacle with identical fields, and a bit-identical gap. During real updates
no vehicle is filed twice or in a stale cell (>5,000 checked queries per
scenario); seeded runs reproduce; unit cases cover cell boundaries, negative
coordinates, overlapping vehicles, empty and single-vehicle scenes and
many-cell moves. A mutation check (an index that drops the nearest vehicle)
fails four of these tests. One real defect fixed: a vehicle with a
non-finite position made `math.floor` raise and would have ended the run;
the full scan ignored such a vehicle (every NaN comparison is false), and
the index now does the same. While building the reference test, its first
version compared `VirtualObstacle`s by identity (they carry a `vehicle_id`
slot); that was the test's error, corrected, not the index's.

Benchmarks re-run (interleaved, same process, 5 pairs, metrics identical in
every pair; median and range):

| Workload (300 s simulated) | Full scan | Index | Ratio |
| --- | --- | --- | --- |
| Saturated signal, 2 lanes, 900 veh/h/arm | 32.2 s (31.4-34.4) | 18.7 s (16.6-19.7) | 1.73x |
| Two-lane roundabout, 800 veh/h/arm | 33.1 s (29.5-43.5) | 25.1 s (24.9-26.4) | 1.31x |

The roundabout's full-scan range is wide (short test and type-check runs
overlapped its later pairs); the index side was stable. Absolute times are
lower than at checkpoint 11 because the machine was less loaded.

**F-64 — observability (ADDED).** `src/observability/` (standard library
only): JSON or plain logs (`LOG_FORMAT`, `LOG_LEVEL`) with the request id on
every line; a redaction filter on every handler and on uvicorn's loggers
(bearer tokens, `uf_pat_` tokens, JWTs, in messages, arguments and
tracebacks); an ASGI middleware that assigns or keeps a safe `X-Request-ID`,
counts requests by route **template** and status class, times them, counts
413/429 refusals by route (resolving the route even when a limit answers
before routing), logs each request (health and metrics scrapes at DEBUG);
job lifecycle in the shared `JobRegistry` (started, completed, cancelled,
failed, refused; durations; outcome "cancelled" read from the job's own
cancel flag); finished registered simulations; authentication failures by a
fixed reason vocabulary; startup and shutdown. `GET /metrics` (Prometheus
text) needs `METRICS_TOKEN` as a bearer token when set, else answers
loopback clients only; nginx does not proxy it. Series per metric are capped
(`MAX_SERIES`, overflow into `other`). Nothing runs per simulation tick.
Tests: `tests/observability/test_observability.py` (22). Found in the live
check and fixed: the first redaction filter collapsed every record's
arguments, which broke uvicorn's access formatter on every request (it reads
the argument tuple); arguments are now redacted element-wise, and a test
formats a record through uvicorn's own `AccessFormatter`.

**F-65 — Copilot evaluation gate (ADDED).** `src/copilot/eval_gate.py`
builds on `copilot-eval-v1` and its scorer: explicit pass/fail checks for
schema and configuration validity (every alternative compiles), a per-item
no-regression baseline on the 20 development items
(`eval/copilot-eval-v1.baseline.json`), held-out items in aggregate only (no
per-item results, so CI cannot become a tuning loop on them), ambiguity,
adversarial safety (a secret planted in the environment is never echoed;
quota bounds), affirmative-claim detection, determinism, entry-model
consistency, and a battery of malformed and hostile inputs. Runs in CI after
the backend tests ("Copilot evaluation (deterministic)", no network or key,
summary in the job summary). `--live` scores the model-backed proposer and
refuses unless `COPILOT_LIVE_EVAL=1`. Tests:
`tests/experiments/test_copilot_eval_gate.py` (9, each check shown to fail on
its defect). No Copilot defect was found by the new checks.

**Browser validation (working tree, ports 8765/5180).** Controls were driven
by DOM events on the controls a user clicks (the pane did not paint, so
pointer clicks were unavailable), and every outcome was checked against the
app's own network traffic, the engine's stream or the server:

| Flow | Result |
| --- | --- |
| Landing / sign-in entry | (checkpoint 11) real Login link, no password field |
| Guided setup, queue with limit 25, over capacity | summary names the queue; radios named and described correctly |
| Run a comparison | the engines' own stream reports `entryModel: "queue"` for both strategies, arrivals = admitted + waiting + rejected |
| Results page | **defect found and fixed**: it did not name the entry model; it now shows a chip from the model the engines report, and flags a run that differs from the request or strategies that disagree (`resultsEntryModel.test.tsx`) |
| Stress Lab suite with the queue | completed (8 runs); result names the model. **Wording defect fixed**: the shared sentence promised a "wait to enter" column the Stress page does not have and contradicted Discovery's objective; now context-specific |
| Discovery Lab with the queue | completed (104 of 134 reserved runs); result names the model and that the objective includes the wait |
| Cancellation | a Stress breakpoint sweep cancelled after a few seconds reads "cancelled" and presents no result; `/metrics` counted it as cancelled |
| Saved-run comparison across models | API `warnings` and the compare page's caution both shown; the config-difference table lists `entryQueue` |
| Phone width (375 px), dark theme | no horizontal overflow, cards stack; dark contrast 8.5-14.8:1. An apparent 1.06:1 reading was a CSS transition frozen in the non-painting pane, confirmed by reading with the transition off |
| Metrics on a real server | `/metrics` answers loopback; job counts matched the three jobs run; access lines redact a JWT in the query string |

A first comparison attempt failed because the dev backend's WebSocket origin
check (correctly) refused the temporary port; the local launch entry was
given that origin, not the code. Temporary launch entries were restored and
no server was left running.

**F-14 — compare tiles capped at 30 fps (RESOLVED, measured).** `SimCanvas`
gained an optional `maxFps`, gated on the shared animation-frame time so
capped canvases repaint on the same frames. Interleaved A/B (production
builds, headless Edge, `scripts/landing_perf.mjs`, 3 runs each), compare
section idle: main-thread task time 435 ms/s (430-443) → 323 ms/s (260-335),
script 311 → 216 ms/s; hero (unchanged code, control) 128 vs 138 ms/s. The
section already rendered at ~32 fps under load, so the visible rate barely
changes; scrubbing and hover update at up to 30 fps. Applied to the four
compare tiles only. Test: `simCanvasFrameCap.test.tsx` (uncapped: 60 paints
per 60 frames; capped: ~30, identical frames across two canvases).

**F-66 — /api/v3 client had no request timeout (FIXED).** F-28 covered
`services/api.ts` only; `services/v3/experiments.ts` (`getJson`/`postJson`,
used by Experiments, Discovery, Stress, tokens) could wait forever. Now
`AbortSignal.timeout(120 s)` with a clear "did not answer in time" message.
Found by reading the unread client code; 33 client and lab tests pass.

**F-67 — live WebSocket could clobber its own replacement (FIXED).**
`services/websocket.ts` closed a socket it was replacing without detaching its
handlers, so that socket's late `close` set the client's current socket to
null and scheduled another reconnect; `connect()` during a pending retry left
the retry armed, opening a second socket. Handlers now act only for their own
socket, replaced sockets are detached first, and a pending retry is cleared.
Tests: two added to `websocket.test.ts` (both fail on the old code).

**F-68 — study polling leaked abort listeners (FIXED).** `studyJobs.ts`
`wait()` added an abort listener per one-second poll and never removed it
when the wait ended (about 3,600 on an hour-long study). Now removed. Test:
`studyJobsPolling.test.ts` (2).

Reviewed with no change: `hooks/useStudyJob.ts` (aborts on unmount and on a
new run; in-flight requests are not tied to the signal, acceptable because
the loop checks it before using a response), `hooks/useWebSocketSnapshot.ts`
(one client per stream mode, disconnected on cleanup, repeated frames
dropped before re-rendering).

### F-09, F-10, F-12 (FIXED)

`scripts/README.md` now indexes every script and documents the root
`src/__init__.py` shim; seven links to the deleted next-generation planning
docs now name the removal commit.

### F-11 — Audit coverage (OPEN)

See [REFACTOR_COMPLETION_AUDIT.md](REFACTOR_COMPLETION_AUDIT.md).

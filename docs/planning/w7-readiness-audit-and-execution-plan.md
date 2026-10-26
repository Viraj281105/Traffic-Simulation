# W7 Readiness Audit and Staged Execution Plan

> **Status:** IMPLEMENTED on branch `viraj-dev` (Stages 0–5; Stage 6 frontend and Stage 7 W5/W6 items remain out of scope) — see [§7 Implementation record](#7-implementation-record). The text below is the original plan; where §7 records a different decision, §7 is what the code does. Audit date 2026-10-23, HEAD at planning time `cac27aa`.
> **Decision:** `CONDITIONAL GO — AUTONOMOUS W7 PLATFORM EXECUTION`
> **Sources:** [sprint plan §1.1, §1.3, §1.5, §3.8](../roadmap/V3_WEEKLY_SPRINT_PLAN.md), [strategy §6, §7, §15](../roadmap/V3_PRODUCT_STRATEGY.md), ADR-013, ADR-017.
> **Authority:** [`docs/roadmap/V3_WEEKLY_SPRINT_PLAN.md`](../roadmap/V3_WEEKLY_SPRINT_PLAN.md) and ADR-013 remain authoritative. Any design proposal here that conflicts with them is flagged as a decision for the Product Owner (PO), not silently adopted.
> Khushi's W5/W6 progress is **not visible** in the repository (remote branches `origin/backend-kk` and `origin/frontend-dev` last changed 2026-09-28 and 2026-09-10). W7 proceeds autonomously without waiting for Khushi; explicit integration seams are preserved without inventing W5/W6 schemas or quota names.

## 1. Repository facts (confirmed)

* W1–W4 are implemented on this branch; the strategy registry is in `backend/src/strategies/` ([builtins.py](../../backend/src/strategies/builtins.py), [registry.py](../../backend/src/strategies/registry.py)).
* No code exists for W5/W6 (no copilot, discovery or proposal module), nor for `.ufpkg`, `zipfile`, PATs or an SDK.
* `/api/v3` has 7 mounted operations: `capabilities`, `experiments/validate`, submit, list, status, result and delete ([router.py](../../backend/src/experiments/router.py)). Pinned in [tests/experiments/test_contract.py](../../backend/tests/experiments/test_contract.py).
* `capabilities()` reports `robustnessExperiments: True`, and reports `experimentCancellation`, `experimentPackages`, `personalAccessTokens`, `pythonClient`, `aiCopilot` and `discoveryLab` as `False` ([service.py](../../backend/src/experiments/service.py)).
* Auth today: every `/api/v3` route uses `get_current_user_id` → `verify_token` (dev token or Cognito JWT) plus router-level `require_api_key` (`X-API-Key` or `Authorization: Bearer <API_KEY>`) mounted in [main.py](../../backend/src/main.py).
* Quotas today: global and per-user active experiments (2 / 1), stored experiments (50), alternatives (6), runs (2,000), simulation steps (2,500,000) ([limits.py](../../backend/src/experiments/limits.py)). Missing: per-token request rate, daily simulated seconds, 1 MB body (delivery layer only, via [request_limits.py](../../backend/src/api/request_limits.py)) and 10 MB package limits.
* Manifest builder: [manifest.py](../../backend/src/experiments/manifest.py) builds `urbanflow-experiment-manifest` v1 with aggression hash and factors; packaging code absent.
* Cancellation: none. Delete refuses queued or running experiments with HTTP 409; `cancel_futures` is used only at process-pool shutdown ([study/runner.py](../../backend/src/study/runner.py)).
* [scripts/v3_demo.py](../../scripts/v3_demo.py) is a stdlib prototype demonstrating submit, polling, report rendering, and checksum checking.

## 2. Dependency summary and integration seams

| Area | Depends on Khushi? | Dependency Type / Integration Seam |
| --- | :---: | --- |
| PATs, scopes, expiry, revocation, audit | **No** | Autonomous; scopes cover v3 routes |
| Robustness quotas and capabilities | **No** | Autonomous |
| AI-call and search-budget quotas | **No (Deferred)** | Seam: extensible quota mapping in `limits.py`; W5/W6 add keys later |
| `.ufpkg` format, export/import/verify for Robustness | **No** | Autonomous; `kind: "robustness_experiment"` |
| Package kinds for Copilot proposal & Discovery | **No (Deferred)** | Seam: open `kind` string + `sidecars[]` metadata slot in manifest |
| Cancel/resume | **No** | Autonomous; core runner & service extension |
| Python client (Robustness, packages, cancel/resume) | **No** | Autonomous stdlib SDK |
| SDK methods for Copilot / Discovery | **No (Deferred)** | Seam: additive client methods when endpoints exist |
| Frontend tokens, quotas, downloads | **No** | **Outside committed 4.25 ED backend budget** (Sprint Plan §1.1) |

No W7 task needs W5/W6 at runtime. W7 defines clean extension seams:
1. An open `kind` field in the package manifest (`kind: "robustness_experiment"` first). **Package compatibility rule:** An open `kind` field does not mean accepting arbitrary unvalidated contents. Unknown kinds receive structural and checksum integrity checks only; full semantic verification strictly requires a recognized registered schema.
2. A generic `sidecars: List[SidecarMetadata]` descriptor list and `sidecars/` ZIP folder convention.
3. An extensible quota dictionary in `limits.py`.
W5 and W6 will define their own schemas and register their quotas when built; W7 does not invent them.

## 3. Staged sequence

### Stage 0 — Contracts and Seams (0.25 ED, shared files: integration owner only)
* **Package manifest extension & ADR-013 versioning check:** Add `kind: "robustness_experiment"` and optional `sidecars[]` metadata array (`name`, `kind`, `path`, `sha256`) to `urbanflow-experiment-manifest` v1 schema under `shared/schemas/v3/`.
  - *ADR-013 Rule Check:* ADR-013 Decision 2 & 6 prescribe `format` + integer `version`, with changes being strictly additive-only.
  - *Compatibility Verdict:* **Backward-compatible; no version bump.** Because `kind` (default `"robustness_experiment"`) and `sidecars` (default `[]`) are optional additive fields with defaults, pre-W7 manifests deserialize cleanly without failure. The integer version remains **`version: 1`**. A bump to `version: 2` would be an unnecessary breaking change and is rejected.
  - *Two-tier verification:* Known kinds require schema-backed semantic verification (`extra="forbid"`); unknown kinds are restricted to structural and integrity verification only.
* **PAT scope list:** Define scopes `experiments:read`, `experiments:run`, `packages:read`, `packages:write`, plus `tokens:read` (list own PATs) and `tokens:manage` (revoke own PATs). Browser sessions hold all scopes; creating a PAT stays browser-session-only, and no scope allows it.
* **Audit vocabulary:** Define event types `token_created`, `token_revoked`, `experiment_submitted`, `experiment_cancelled`, `quota_rejected`, and `auth_failed` (failed authentication: audited per request when it names a real revoked/expired token, otherwise once per client lockout; `uf_audit_log` is append-only via UPDATE/DELETE-rejecting triggers, which do not protect against someone with write access to the database file).
* **API Route Signatures:** Codify route paths, methods, status codes, and openapi descriptions for Stages 1–4.
* **Autonomous execution:** Per ADR-013 (Decision 8), the integration owner (Viraj) updates shared contracts. Khushi is notified asynchronously of the integration seams via GitHub issue/PR note; no blocking synchronous meeting.
* *Acceptance:* Schemas committed; contract tests pass with new optional fields tolerating `null`.

### Stage 1 — PATs, scopes, revocation, audit (1.5 ED)
* Depends on Stage 0.
* **Storage & Crypto:** SQLite table `uf_pats` (short id `pat_xxx`, user_id, name, sha256_hash, scopes_json, created_at, expires_at, revoked_at, last_used_at). 256-bit cryptographically secure secret shown **once** upon creation. Mandatory expiry: default 30 d, maximum 90 d. At most 10 active tokens per user.
* **Audit Table:** Append-only SQLite table `uf_audit_log` (id, timestamp, user_id, token_id, event_type, details_json). Records token lifecycle and quota rejections without payloads or secrets.
* **HTTP Endpoints:**
  - `POST /api/v3/tokens`: Create token. **Restricted to authenticated browser sessions** (Cognito JWT or dev bypass). A request presenting a PAT is rejected with HTTP 403 ("A PAT cannot create a PAT"). Returns secret once.
  - `GET /api/v3/tokens`: List caller's active tokens (masked/short id, name, scopes, expiry, last used).
  - `DELETE /api/v3/tokens/{token_id}`: Revoke a token immediately.
* **Authentication & Authorization Dependency Pipeline (4 distinct stages):**
  1. *Infrastructure API-Key Validation (`require_api_key` router dependency):*
     - Protects deployment boundary (see `security.py:15`).
     - *Nginx-proxied requests:* Nginx automatically sets `proxy_set_header X-API-Key "${BACKEND_API_KEY}"`; validation passes transparently while forwarding `Authorization: Bearer <TOKEN>`.
     - *Direct backend requests:* In local development (`API_KEY` unset), validation is a no-op. In locked-down environments (`API_KEY` set), trusted internal SDK clients may supply `X-API-Key` through secure deployment configuration.
     - *SDK Distribution & External Access Constraint:* Distributable SDKs must never embed or expose the shared infrastructure API key. External SDK clients must use an approved gateway or another explicitly documented access pattern that preserves `require_api_key` without exposing infrastructure secrets. `require_api_key` must **not** be weakened to accept arbitrary PAT strings as substitutes for the infrastructure API key.
  2. *User Authentication (`get_current_identity` auth dependency):*
     - Extracts bearer token from `Authorization: Bearer <TOKEN>` (never URLs/query params).
     - Resolves into unified `UserIdentity(user_id, auth_type, token_id, scopes)`:
       * `DEV_AUTH_BYPASS=1` & token == `DEV_AUTH_TOKEN` -> `auth_type="dev"`, `user_id="local-dev"`, full scopes.
       * Cognito JWT -> verifies RS256 JWKS signature and `aud` -> `auth_type="cognito"`, `user_id=claims["sub"]`, full scopes.
       * PAT (`uf_pat_...`) -> SHA-256 hash lookup in `uf_pats`. Asserts active, not expired (`expires_at > now`), not revoked (`revoked_at is null`). Updates `last_used_at`. -> `auth_type="pat"`, `user_id=row["user_id"]`, `token_id=row["id"]`, `scopes=row["scopes"]`.
       * Missing or invalid token -> HTTP 401 Unauthorized.
       * Rate limiting on invalid attempts tracked per client IP (`client_key(request)`).
  3. *PAT Scope Authorization (`require_scope` dependency):*
     - Enforced per route (e.g. `Depends(require_scope("experiments:run"))`).
     - If `auth_type` in `("cognito", "dev")`: passes automatically (browser/dev sessions hold full interactive permissions).
     - If `auth_type == "pat"`: asserts required scope ∈ `identity.scopes`. Rejects with HTTP 403 Forbidden ("Insufficient token scope") if missing.
     - Creation restriction: `POST /api/v3/tokens` enforces `auth_type != "pat"` (rejects with HTTP 403 "A PAT cannot create a PAT").
  4. *Resource Ownership Enforcement:*
     - Service and store methods filter all queries by `identity.user_id`.
     - Accessing or modifying another user's resource returns HTTP 404 Not Found (ADR-013 Decision 5: another user's id is indistinguishable from non-existent).
* *Tests:* Token lifecycle, immediate revocation, expiry, scope denial per route (extend `test_v3_route_auth.py`), PAT self-creation refusal, log redaction, audit table append-only verification, existing auth suites (`test_v2_route_auth.py`, `test_api_key_auth.py`) unmodified and green.
* *Compatibility:* `/api/v1` and `/api/v2` frozen behavior untouched (continue to use `get_current_user_id` without scope restrictions). ADR-018 layering preserved (delivery logic in `src/api/auth.py` and `src/api/security.py`, no SQL in routers).

### Stage 2 — Quotas and capabilities (0.5 ED)
* Depends on Stage 1.
* **Quotas Added:**
  - Per-token request rate: 60 requests per minute per token.
  - Daily simulated seconds: 86,400 s (24 hours of simulated time) per user per day.
  - Package size: 10 MB maximum.
* **Persistence:** Track simulated seconds per user in SQLite (`uf_usage` or daily aggregation of completed `uf_experiments` within current UTC day) so single-process uvicorn restarts do not reset usage counters.
* **Enforcement:** Enforce quotas at submission and during execution. Return HTTP 429 (rate/volume), HTTP 413 (body/package size), or HTTP 422 (experiment complexity) naming the exceeded quota.
* **Capabilities:** Expose new quota values in `GET /api/v3/capabilities`. Capability flags flip to `True` only when the underlying feature is functional.
* *Tests:* Quota rejection names exceeded quota; simulated seconds persist across restart; capabilities reflect accurate state.

### Stage 3 — Cancel and resume (0.25 ED — provisional / unvalidated)
* Moved before Python SDK so the SDK implements and tests the complete API surface in one pass.
* **Effort warning:** 0.25 ED is only ~1.5 focused hours. Given deterministic resumption, task cancellation, state persistence, and concurrency synchronization, treat this estimate as **unvalidated** until implementation complexity is assessed in code. If complexity expands, draw from the weekly 15% contingency buffer (Sprint Plan §1.2).
* Depends on Stage 0; touches `src/experiments/service.py` and `src/uncertainty/runner.py`.
* **HTTP Endpoints:**
  - `POST /api/v3/experiments/{experiment_id}/cancel`: Sets status to `cancelled`. Signals running tasks to stop. Leaves a consistent *incomplete* result record (conditions completed so far are preserved; incomplete conditions excluded with reason `incomplete_cancelled`).
  - `POST /api/v3/experiments/{experiment_id}/resume`: Resumes a cancelled or interrupted experiment. Re-runs remaining planned tasks using the exact deterministic seed rule: `(base seed, condition index, replication)`. Resumed result reproduces the uninterrupted fingerprint.
  - `DELETE /api/v3/experiments/{experiment_id}`: Updated to allow deleting experiments in `cancelled` state (queued/running still require cancellation first).
* *Tests:* Cancel while queued; cancel while running; delete after cancel; cancel/resume equivalence (resumed fingerprint equals uninterrupted run); ownership enforcement.

### Stage 4 — `.ufpkg` export, import, verify (1.25 ED)
* Depends on Stage 0; parallel to Stage 2/3.
* **HTTP Endpoints:**
  - `GET /api/v3/experiments/{experiment_id}/package`: Exports a ZIP archive containing `manifest.json`, `experiment.json`, `result.json`, `SHA256SUMS`, and optional sidecars.
  - `POST /api/v3/packages/verify`: Accepts an uploaded `.ufpkg` file, validates internal integrity, compares fingerprints and replay conditions, and returns verification report without executing anything.
* **Import & Verification Security:**
  - Archive file size limit: 10 MB (`MAX_PACKAGE_BYTES = 10 * 1024 * 1024`).
  - Decompression bomb protection: Maximum uncompressed size: 50 MB; maximum entry count: 50 files.
  - Path traversal / Zip-slip rejection: Validate all member paths; reject `..`, absolute paths, leading slashes, Windows drive letters (`C:`), or backslashes.
  - In-memory inspection: Process archive via `zipfile.ZipFile(io.BytesIO(...))` without extracting files to disk.
  - Filename allow-list: `^[a-zA-Z0-9_.-]+$`. Reject any executable extensions (`.py`, `.sh`, `.exe`, `.bat`, etc.).
  - **Two-tier verification:**
    * *Structural & Integrity checks (all packages):* Archive size, decompression limits, traversal checks, filename allowlist, manifest presence, per-file SHA-256 match.
    * *Semantic verification (known kinds only):* Recognized kinds (`robustness_experiment`) undergo full JSON Schema validation with `extra="forbid"`. Packages with unknown `kind` values receive structural and checksum integrity verification only; the report states semantic validation was skipped due to an unrecognized kind.
  - Checksum verification: SHA-256 computed on normalized LF bytes.
  - Provenance check: Mandatory source and environment metadata.
  - Replay evaluation: Output reports exactly one of `exact`, `comparable`, or `differs (engine or runtime changed)`.
  - Normative statement: Verifier states *"Integrity is not authenticity: checksums show a package is internally consistent, not who made it."*
* *Tests:* Tampered package rejected; zip bomb (> 50 MB) rejected; zip-slip traversal rejected; round trip of W1 demo experiment; replay classification; unknown kind structural-only verification.

### Stage 5 — Python client / SDK (0.5 ED)
* Depends on Stages 1–4.
* Productise `scripts/v3_demo.py` into an importable client library and CLI:
  - Supports PAT authentication header (`Authorization: Bearer <PAT>`).
  - Methods: `submit()`, `status()`, `wait_with_progress()`, `cancel()`, `resume()`, `result()`, `export_package()`, `verify_package()`.
  - Standard library only (or pinned `httpx`), zero unapproved external dependencies.
  - Secret hygiene: Distributable SDK packages must never embed or expose the shared infrastructure API key. Trusted internal environments may supply `X-API-Key` via secure deployment configuration.
* *Tests:* Integration test against a live local backend; contract validation against `shared/schemas/v3/openapi.v3.snapshot.json`; CLI error handling.

### Stage 6 — Frontend (Outside committed 4.25 ED backend budget)
* **Capacity Rule:** Per Sprint Plan §1.1 and §3.8, committed capacity for W7 is **4.25 ED for one engineer**. Squeezing a full frontend token management UI, quota dashboard, package uploader, and cancel controls into backend security budgets creates unbudgeted scope.
* **Boundary:** Gate **G-B1** is satisfied by the backend API and Python SDK. Frontend implementation is scheduled as a companion task assigned to frontend capacity (khushik8605 or separate PO allocation).
* When implemented: Token management view, capability/quota indicator, package download button, cancel/resume buttons. Accessible (axe clean) and respects `/api/v3/capabilities` flags.

### Stage 7 — Deferred until W5/W6 implementations exist
* Copilot proposal sidecar schema and Discovery candidate package kinds.
* AI-specific quota entries (`proposalsPerDay`, `tokensPerDay`, spend cap) and search budget quotas.
* SDK methods for `copilot_propose()` and `discovery_search()`.
* Checkpoints: G-AI-A (3 Dec) and G-AI-B (10 Dec). If absent when W7 starts, W7 ships Robustness platform features cleanly and records the rest as carried forward.

## 4. Security and compatibility notes

* **PAT Storage & Transit:** SHA-256 hashed storage with unique short ID; 256-bit entropy; tokens accepted in `Authorization` header only; strictly redacted from logs.
* **API Key & PAT Coexistence:** Nginx injects `X-API-Key` for browser proxying. In locked-down environments (`API_KEY` configured), trusted internal SDK clients may supply `X-API-Key` through secure deployment configuration. Distributable SDKs must never embed or expose the shared infrastructure API key. External SDK clients must use an approved gateway or another explicitly documented access pattern that preserves `require_api_key` without exposing infrastructure secrets. `require_api_key` remains an independent infrastructure guard and is not weakened.
* **Execution & Execution Boundaries:** No arbitrary code execution, no uploaded scripts, no webhooks (permanent V3.0 exclusions per Strategy §7).
* **Single-Process Quota Limitation:** In-process quota tracking is an accepted limitation for single uvicorn instances (ADR-013). Daily quotas persist to SQLite to survive process restarts.
* **Shared Files Governance:** In accordance with ADR-013 (Decision 8), changes to `backend/src/main.py`, `shared/schemas/**`, database migrations, and `openapi.v3.snapshot.json` are made exclusively by the integration owner.

## 5. Downstream alignment

* **W8 (Conditional Stress-Testing):** Independent of W5/W6; depends on W7 quota enforcement and cancellation handling.
* **W9 (Release Candidate):** Evaluates studies E1–E4. Package verifier built in W7 verifies evaluation packages E1 and E2 immediately; E3/E4 packages plug into the sidecar seam when W5/W6 arrive.

## 6. Open items and governance flags

* **Cancel/Resume Complexity Assessment:** 0.25 ED (1.5 h) is unvalidated. Given the combination of task interruption, process pool mechanics, SQLite state tracking, and deterministic seed resumption, assess implementation complexity early in Stage 3 and draw from the 15% weekly contingency buffer if needed.
* **Governance Flag (Frontend Capacity):** Frontend ownership (khushik8605 vs Viraj281105) must be formally confirmed by the PO. If assigned to Viraj, frontend work must be funded from separate capacity or contingency buffer, not compressed into the 4.25 ED backend platform budget.
* **W4 PO Sign-Off:** High-aggression default (ADR-016 / ADR-019) sign-off at gate G-AG is tracked separately and does not block W7 development.
* **Unresolved Architecture Decision (External SDK Access Pattern in Locked-Down Environments):** The repository defines Nginx reverse proxying for containerized web traffic (`frontend/templates/default.conf.template`) and trusted internal `X-API-Key` passing, but does not establish an external gateway topology or edge access pattern for distributable SDK clients operating outside the private network in production. `require_api_key` cannot be weakened to accept PATs, and distributable SDKs must never embed or expose shared infrastructure secrets. The Product Owner and infrastructure team must formally decide on the external-client access pattern (e.g. an edge gateway endpoint that injects `BACKEND_API_KEY` or a dedicated ingress proxy) prior to public SDK distribution.

## 7. Implementation record

What was built, where it departs from the plan above, and what is still open. Tests named here run in the
backend virtual environment (`pytest --no-cov`); the SDK's own unit tests run from `sdk/python`.

### 7.1 Delivered

| Stage | Delivered | Main files |
| --- | --- | --- |
| 0 | Manifest `kind`/`sidecars`, two-tier validation, PAT scopes, audit vocabulary, route contracts | `experiments/manifest.py`, `api/contracts_v3.py` |
| 1 | PATs (SHA-256 at rest, shown once, 1–90 days, max 10 active, atomic quota), scopes incl. `tokens:read` / `tokens:manage`, browser-session-only creation, ownership 404s, failed-auth auditing, append-only `uf_audit_log`, trusted-proxy client identity | `api/auth.py`, `api/token_store.py`, `api/tokens_router.py`, `api/audit.py`, `api/request_limits.py` |
| 2 | Per-token 60 requests/minute, 86,400 simulated seconds per user per UTC day (persisted in `uf_usage`), 10 MB package limit; all reported by `GET /api/v3/capabilities`, whose feature flags are now true only for what exists | `experiments/limits.py`, `experiments/store.py`, `api/auth.py` |
| 3 | `POST /experiments/{id}/cancel` and `/resume`; delete allowed after cancel | `experiments/service.py`, `study/runner.py`, `uncertainty/runner.py` |
| 4 | `GET /experiments/{id}/package`, `POST /packages/verify`, safe extraction helper | `experiments/package.py`, `experiments/router.py` |
| 5 | Standard-library client and CLI, `sdk/python` (`urbanflow_client`) | `sdk/python/` |

### 7.2 Decisions recorded (where the plan was silent or is refined)

* **Cancel/resume is real, within one limit.** Every simulation run is a deterministic function of the
  specification, so a cancelled experiment keeps the metrics of the runs that finished (its *checkpoint*, kept
  in `uf_experiments.checkpoint_json`) and a resume simulates only the rest; the completed result has the same
  `resultFingerprint` as an uninterrupted run (tested on the fake executor and on the real process pool).
  The limit: a simulation already running in a worker cannot be interrupted, so a cancelled experiment stays
  counted as active, and cannot be deleted or resumed, until the runs in flight finish (seconds to a minute).
  Status goes to `cancelled` at once; a repeated cancel is a harmless 202. Failed runs are not checkpointed and
  run again on resume. Failed and completed experiments cannot be cancelled or resumed (409). Allowed
  transitions: `queued|running → cancelled → queued → running → completed|failed|cancelled`.
* **The result of a cancelled experiment** is an `urbanflow-experiment-partial-result` (not an
  `urbanflow-experiment-result`): finished conditions analysed, unfinished ones excluded as
  `incomplete_cancelled` (a new member of `EXCLUSION_REASONS`), no `resultFingerprint`, no manifest, not
  exportable.
* **Daily simulated seconds** are *reserved* up front (`duration × total runs`), atomically (`BEGIN IMMEDIATE`),
  so execution can never exceed the quota; a cancellation refunds the runs that never ran and a resume reserves
  only the remainder. An experiment larger than a whole day is refused with 422, not 429. If SQLite is
  unavailable the counters fall back to process memory.
* **Per-token rate** is a sliding 60 s window per PAT id and is process-local (like the failed-auth counters).
  Browser sessions (dev, Cognito) are not limited by it.
* **Package layout** is `manifest.json`, `experiment.json`, `result.json`, `SHA256SUMS` and optional
  `sidecars/<file>` (`.json`, `.csv`, `.txt`); the plan's flat allow-list regex is applied to each path segment
  and one `sidecars/` level is allowed because the manifest contract names that folder.
* **Checksums are over the exact member bytes**, not LF-normalised bytes (the plan's wording): export always
  writes LF, and a package re-saved with CRLF fails verification rather than silently passing. `SHA256SUMS` is
  authoritative for every member; the manifest's `sidecars[].sha256` and `packageChecksums` must agree with it.
* **Executable content** is refused by allow-list (names and extensions) *and* by leading bytes (PE, ELF,
  `#!`, Mach-O, Java class, ZIP, gzip, 7z, RAR), and sidecars must be UTF-8 text without NUL bytes.
* **Verification is fingerprint-aware**: besides digests, the verifier recomputes the specification, scenario
  and result fingerprints from the packaged documents and compares them with the manifest, so a package whose
  analysis was edited and whose checksums were regenerated is still rejected.
* **`replayClass`** is derived from recorded provenance, never by re-running: `exact` = same code revision,
  Python version and driver-aggression parameters as this server; `comparable` = same aggression parameters and
  Python minor version but a different or unrecorded revision; `differs (engine or runtime changed)` otherwise
  and for unknown kinds (where replay evaluation is skipped). It states how likely an identical replay is, not
  that it was reproduced.
* **"Import" is verification.** `POST /packages/verify` inspects an upload in memory and stores nothing; no
  endpoint ingests a package into the experiment store or runs it. `extract_package` exists for a future local
  importer and re-validates every resolved target against the extraction root, creating files exclusively.
* **`POST /packages/verify` needs `packages:write`** as the contract fixed; export needs `packages:read`.
* **Audit vocabulary** gained `auth_failed`, `package_exported` and `package_verified`; `experiment_cancelled`
  is now emitted. Audit writes on the experiment routes never fail the request.
* **Upload**: the raw request body (`application/octet-stream`), capped at 10 MB by the body-size middleware for
  `/api/v3/packages` only, and held in a compute slot while it is inspected.

### 7.3 Still open (deployment and design)

* **Trusted proxy.** Compose pins the nginx container to `172.30.77.10` on a private network and trusts that one
  address; behind a further load balancer nginx needs its real-IP module configured, which is not done here
  ([operations guide](../operations.md#request-and-workload-limits)). Verify two visitors get distinct
  identities after deploying.
* **Process-local counters.** Failed-auth, per-token-rate and in-memory usage fallback counters belong to one
  backend process; with several workers each would allow its own share. A shared store is a later decision.
* **Audit tamper limits.** The append-only triggers stop SQL on the schema, not someone with write access to
  the database file.
* **External SDK access pattern** (above, §6) is still undecided: the SDK does not embed the infrastructure API
  key and accepts one only through configuration for trusted internal use.
* **Frontend (Stage 6)** and **W5/W6 items (Stage 7)** are not implemented; capabilities report `aiCopilot` and
  `discoveryLab` as false.
* **Not exercised here:** the Docker network and live nginx identity (only `docker compose config` and a probe
  network were checked), multi-worker behaviour, and a package produced on another machine.

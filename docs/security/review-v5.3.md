# Security review V5.3 (package 2F, W53)

Date: 2026-11-05. Method: an automated checklist in `backend/tests/security/` and
`scripts/dependency_audit.py`, plus a manual read of the routers, auth, tenancy, run store,
MQTT adapter, Terraform and the nginx template. Source under `backend/src` was not changed.
Companion document: `threat-model.md`.

## What runs in CI

| File | What it enforces |
|---|---|
| `tests/security/test_route_auth_sweep.py` | Walks every route of the real app (including nested routers and WebSockets). A request with no key and no token must get 401 or 403 unless the route is in a reviewed allow-list with a reason. A new unguarded route fails by name. Also fails on stale allow-list entries. |
| `tests/security/test_input_bounds.py` | 40 out-of-range and oversized requests to the stateless `/api/v2` POST endpoints with a valid test identity: 422 (or 413), within 5 s, never 500. |
| `tests/security/test_secrets_scan.py` | `git ls-files` scan for private keys, AWS key ids, JWT-shaped tokens, long bearer tokens and quoted passwords. Allow-list with reasons. Skips without git. |
| `tests/security/test_headers_and_errors.py` | No traceback or path in 404, 405, 401, 422 or 500 bodies; token not echoed; request id; CORS does not reflect a foreign origin with credentials; foreign-origin WebSocket refused; nginx template headers. |
| `tests/security/test_session_isolation.py` | Anonymous cookie must not select a signed-in user's live session. |
| `tests/security/test_dependency_audit.py` and `scripts/dependency_audit.py` | Every runtime and dev pin uses `==`, no duplicates, curated risky-package table. `--installed` compares with `pip list`. |

Findings that are real are marked `xfail(strict=True)` with the finding id, so CI stays green
and the finding stays visible: when the source is fixed the test XPASSes and strict mode fails
the run until the marker is removed.

## Findings

Severity is a judgement from reading the code, not from exploitation.

| Id | Severity | Finding | Evidence | Recommended fix | Test |
|---|---|---|---|---|---|
| S-01 | Medium | Seven `/api/v2` families (network-metrics, network-graphs, calibration, twin, incidents, priority, v2x, jobs) are outside the 1 MiB body cap, so an authenticated caller can make the server read an arbitrarily large body into memory before validation. The cap list stops at `/api/v2/networks`, `/api/v2/planning/validate` and `/api/v3/*`. Calibration legitimately takes an 8 MB counts file, so it needs its own larger limit rather than the default. | `backend/src/api/request_limits.py:59-66` (`LIMITED_PREFIXES`); `src/calibration/network_calibration_router.py:35` (8 MB field) | Cap `/api/v2/` as a whole at 1 MiB and give `/api/v2/calibration` a `PREFIX_LIMITS` entry of about 9 MiB. | `test_input_bounds.py::test_body_over_one_mebibyte_is_413` (xfail, 7 params) |
| S-02 | Medium | The four simulation WebSockets accept clients with no API key and no token. The only check is `Origin`, and a handshake with no `Origin` header is allowed by design, so any script can connect and, without a cookie, is attached to the shared "default" live session. | `src/api/origins.py:33-41`; `src/api/ws_origin.py:38`; `src/live/router.py:305-310`, `:420-425`, `:572-578`; `src/simulations/router.py:338-345` | Require a short-lived ticket (issued by an authenticated HTTP call) or the verified token as a query/subprotocol value before `accept()`; stop falling back to the shared "default" session for anonymous sockets. | `test_route_auth_sweep.py::test_websockets_require_credentials` (xfail, 4 params) |
| S-03 | Medium | Live-session keys are not namespaced: an anonymous request's `ts_session` cookie is used verbatim as the key, and a signed-in user's session is keyed by their Cognito `sub` in the same dict. Anyone who learns a user's `sub` can send it as the cookie and operate that user's live simulation (no token needed on the cookie path). | `src/live/sessions.py:241-247`, `:190-200` | Prefix keys (`anon:<uuid>` versus `user:<sub>`) and mint anonymous ids server-side only, rejecting client-chosen values that are not in the registry. | `test_session_isolation.py` (xfail) |
| S-04 | Medium | The MQTT adapter can only connect in plaintext without credentials: no TLS context, username/password or client-certificate option, and no topic ACL guidance. Fine for the in-process bus the API uses; unsafe as a deployment path. `paho-mqtt` is also not pinned in any requirements file. | `src/v2x/mqtt_bus.py:55-73` (`__init__`, `connect`) | Add `tls`, `username`, `password` parameters (sourced from Secrets Manager), refuse non-TLS hosts unless an explicit local flag is set, document broker ACLs per topic prefix, pin `paho-mqtt`. | none (design finding) |
| S-05 | Medium | Tenant isolation is not wired into any data path. The tenancy layer is documented as additive; run-store keys are `runs/<run_id>/...` with no tenant segment, and no router outside `/api/v2/tenancy` uses `TenantScope`. The W53 goal "two tenants cannot see each other's data" is therefore not met by the current code, only by the layer's own unit tests. | `docs/security/tenancy.md:4,116`; `src/runstore/store.py:30,80-84`; `src/main.py:154-158` is the only mount | Adopt `ctx.scope.key_for(...)` in the run store and `sql_filter` in the DAOs, then add an end-to-end two-tenant test over the real routes. | none (needs product decision on scope) |
| S-06 | Low | Registered simulations, study jobs and sweeps are readable by id (and the sweep list by anyone) with no key, token or owner check. Ids are unguessable for simulations, but the sweep list enumerates them. Results may contain another user's configuration. | `src/simulations/router.py:239-281`; `src/study/router.py:278-298`; allow-listed in the sweep with this id | Require the user dependency and filter by owner, as run history does (`src/access.py`). | allow-list entries in the sweep |
| S-07 | Low | With `COGNITO_USER_POOL_ID` unset, any presented token yields 500 and the text "Cognito User Pool ID not configured on server". Fail-closed, but it discloses configuration and is the wrong class of status. | `src/api/auth.py:365-368` | Return 503 with a generic message and log the detail. | `test_headers_and_errors.py::test_unconfigured_identity_provider_is_not_a_500` (xfail) |
| S-08 | Low | Unset `API_KEY` disables the key guard entirely (intended for local development). A production deployment that forgets the variable silently loses one of the two guards. | `src/api/security.py:48-49` | Refuse to start (or log an error banner) when `ENVIRONMENT=production` and `API_KEY` is empty. | none |
| S-09 | Low | The API process sets no security headers of its own, and HSTS is set by neither the API nor the nginx template. `/docs`, `/redoc` and `/openapi.json` are public. Behind the shipped nginx the other baseline headers are present. | `frontend/templates/default.conf.template:13-24` (no `Strict-Transport-Security`); `src/main.py` | Add `Strict-Transport-Security` at the TLS terminator; consider disabling docs routes in production. | nginx header asserts in `test_headers_and_errors.py` |
| S-10 | Low | The EKS module defaults the public API endpoint to `0.0.0.0/0` (IAM-authenticated, but reachable from anywhere). | `infra/terraform/modules/eks/main.tf:38-48` | Set `public_access_cidrs` to the CI runner ranges or use private endpoint plus a self-hosted runner. | none |
| S-11 | Low | `requirements-rl.txt` uses ranges (`>=`), and the dependency script flags it; `boto3 1.34.0` / `botocore 1.34.162` are older than two years. Not part of the CI install, but not reproducible either. | `backend/requirements-rl.txt:9-12`; `backend/requirements.txt:46-47` | Pin with a lock file; schedule a boto refresh. | `scripts/dependency_audit.py --all` reports them |
| S-12 | Info | CORS allows all methods and headers; credentials are enabled only for the explicit origin list (never with `*`). | `src/main.py:89-94` | None required; tighten methods to those used. | CORS check in `test_headers_and_errors.py` |
| S-13 | Info | `/metrics` without `METRICS_TOKEN` trusts the peer address being loopback. A reverse proxy on the same host would make every client look local. nginx does not proxy `/metrics` (asserted). | `src/observability/router.py:80-89` | Set `METRICS_TOKEN` in every deployed environment. | sweep and nginx assert |
| S-14 | Info | Local virtualenv drift: `numpy` installed 2.5.4 vs pinned 2.3.5. | `scripts/dependency_audit.py --installed` | Rebuild the venv; CI installs from the pins so it is unaffected. | n/a |

### Checked and found sound

- Every route outside the 31 allow-listed HTTP routes and 4 WebSockets rejects an
  unauthenticated request (about 200 route methods); the allow-list names a reason for each.
- All `/api/v2` POST bodies tried (40 cases) answered 422 in under a second; malformed JSON,
  non-object JSON and wrong types never produced a 500.
- Error bodies, including a forced unhandled exception, carry no traceback or path.
- No secrets matched in tracked files after three reviewed false positives (a documentation
  line quoting a PEM header, an HTML `autoComplete` attribute, a fixture token in SDK tests).
- Pinned runtime dependencies are not below any version in the curated table.

## NOT REVIEWED

- No penetration test and no dynamic scanning (no fuzzing, no authenticated scanner, no load or
  abuse testing).
- No real AWS: Terraform was read, never planned, validated or applied; IAM trust policies, the
  CI workflow secrets handling, S3 lifecycle and bucket policies in a live account, RDS
  parameter groups and network ACLs are unverified.
- No dependency CVE database lookup: the audit is offline against a small curated table; a clean
  result does not mean no known CVEs. Run `pip-audit` or OSV/Dependabot for that. Frontend
  (npm) and Go (`go.sum`) dependencies were not audited.
- The frontend source (token storage, XSS sinks, routing) and the Go consumer beyond a grep.
- The MQTT broker and Redpanda in a running state; Helm charts; container image scanning.
- Cognito configuration itself (password policy, MFA, token lifetimes, the tenant custom
  attribute).
- Authorization of routes with a valid but low-privilege identity (role matrix enforcement per
  route) and cross-user access with two real identities, beyond the existing tests in
  `tests/api`.
- Timing and side-channel behaviour, denial of service at scale, and supply-chain integrity of
  the build.

# Threat model (STRIDE), V5.3

Scope: the components that exist in this repository on 2026-11-05. It is a desk analysis from
reading the code and the infrastructure files; nothing was attacked and no AWS account was
touched (see "Not reviewed" in `review-v5.3.md`). Finding ids (S-nn) refer to that document.
The automated checks that back this model are in `backend/tests/security/`.

## Components and trust boundaries

```
 Browser --TLS--> nginx (frontend image) --HTTP--> API (FastAPI, backend/src/main.py)
                                                     |        |            |
                                    SQLite / RDS <---+        |            +--> job queue (SQS) --> worker
                                                              +--> run store (S3 / local files)
 Cognito / OIDC issuer --JWKS--> API          MQTT broker <--> V2X adapter      Redpanda --> Go consumer
 Terraform --> AWS (VPC, EKS, RDS, S3, SQS, IAM, Secrets Manager)
```

Boundaries: internet to nginx; nginx to API (nginx adds `X-API-Key`, so the key identifies the
proxy, not a person); API to identity provider; API to storage and queue; broker and Redpanda
to their consumers; CI to AWS.

## Controls that exist today (what the table below relies on)

- Two guards on every `/api/v2` and `/api/v3` route: API key and a verified user token
  (`src/api/security.py`, `src/api/auth.py`), checked for every route by the sweep.
- RS256-only JWT verification with issuer and audience checks (`src/api/auth.py`,
  `src/tenancy/oidc.py`); the development token is refused unless `DEV_AUTH_BYPASS` is set.
- A 1 MiB body cap on part of `/api/v2` (`src/api/request_limits.py`), pydantic bounds on
  request models, and a 2-slot gate on synchronous compute (`compute_slot`).
- A generic error envelope with no traceback; token redaction in logs
  (`src/observability/logging_setup.py`); a request id on every response.
- Origin check on the simulation WebSockets (`src/api/origins.py`).
- Terraform: S3 public-access block and versioning, encrypted RDS and SQS, private RDS, KMS for
  EKS secrets, a tag module.

## STRIDE by component

S spoofing, T tampering, R repudiation, I information disclosure, D denial of service, E
elevation of privilege. "Gap" rows link to a finding; "ok" rows name the control and, where
there is one, the automated check.

### API (FastAPI)

| | Threat | Status |
|---|---|---|
| S | Caller forges a user token or reuses the dev token | ok: RS256 + issuer/audience; dev token refused without the bypass (`tests/api/test_v2_route_auth.py`) |
| S | Anonymous client adopts another user's live session by sending their key as the `ts_session` cookie | gap S-03 (`test_session_isolation.py`, xfail) |
| T | Body or query values out of range steer a long run | ok: pydantic bounds, 422 within budget (`test_input_bounds.py`) |
| R | No per-user audit trail of who started which run | partial: request log has a request id, but not the user id on every line; not assessed further |
| I | Error text leaks paths or tracebacks | ok (`test_headers_and_errors.py`); misconfiguration message leak S-07 |
| I | Anonymous reads of simulations, sweeps, jobs by id | gap S-06 |
| D | Oversized body read in full before validation | gap S-01 (7 of 9 `/api/v2` families uncapped) |
| D | Many synchronous runs starve workers | ok: `compute_slot`, per-client limit; async jobs capped |
| E | New route shipped without guards | ok: the sweep fails by route name (`test_route_auth_sweep.py`) |
| E | `API_KEY` left unset in a deployment disables the key guard | gap S-08 (documented default, no startup check) |

### Workers and job queue (`src/jobs`, SQS)

| | Threat | Status |
|---|---|---|
| S | Forged queue message | not assessed beyond schema: relies on IAM on the queue (Terraform `modules/sqs`, `iam`) |
| T | Job spec carries unbounded work | ok: `JobSpec` bounds (`numSeeds` <= 100, duration limits), 200 KiB message cap, `extra="forbid"` (`test_input_bounds.py`) |
| T | Tenant or tag injection into queue attributes | ok: tenant regex, cost-tag validation |
| R | Replay of a message | ok in design: idempotency key, max receives, DLQ; not load tested |
| I | Message contents readable at rest | ok: SQS managed SSE |
| D | Poison message loops | ok: `max_receives` and DLQ |
| E | Worker role broader than needed | not reviewed beyond a read of `modules/iam` |

### Run store (S3 / local) (`src/runstore`)

| | Threat | Status |
|---|---|---|
| S | n/a, accessed with the workload role | |
| T | Run id escapes the prefix | ok: `validate_run_id` allows letters, digits, `-`, `_` |
| T | One tenant overwrites another's run | gap S-05 (keys are `runs/<run_id>/...`, not tenant-scoped) |
| I | Cross-tenant read | gap S-05 |
| I | Bucket made public | ok: public-access block, versioning, encryption in `modules/storage` |
| D | Unbounded growth | not assessed (lifecycle rules not checked) |

### OIDC and tenancy (`src/tenancy`)

| | Threat | Status |
|---|---|---|
| S | Token from another issuer or app client | ok: issuer, audience or `client_id` checked |
| S | Algorithm confusion | ok: RS256 only |
| T | Tenant id in claim used to build keys or SQL | ok in the layer (strict regex, `TenantScope`); not yet used by data routes (S-05) |
| I | Cross-tenant data | gap S-05: the layer is additive and unadopted |
| D | Rate and quota abuse | ok in the layer (limits, quotas); applies only where adopted |
| E | Role escalation through groups | ok: unknown groups give no permissions; admin is per tenant |

### MQTT / V2X (`src/v2x`)

| | Threat | Status |
|---|---|---|
| S | Anyone on the broker publishes as a vehicle or signal | gap S-04: adapter has no TLS, username or ACL options |
| T | Message modified in transit | gap S-04 (plaintext port 1883) |
| I | Positions and speeds readable on the wire | gap S-04 |
| D | Flood of malformed payloads | partial: adapter counts rejected messages; no rate limit |
| Note | The HTTP experiment endpoint uses an in-process bus, so the API itself is not exposed to this path |

### Redpanda consumer (`docker-compose.redpanda.yml`, `services/consumer-go`)

| | Threat | Status |
|---|---|---|
| S/T/I | Unauthenticated, unencrypted broker | accepted for dev: bound to 127.0.0.1, labelled "not for production" |
| D | Oversized message | partial: reader `MaxBytes` 10 MiB; JSON decode error is handled per message |
| E | Container privileges | ok: distroless nonroot image |
| | Go build and Helm were not run (see the execution plan) | not reviewed |

### Terraform-provisioned AWS (`infra/terraform`, `.github/workflows/aws-staging.yml`)

| | Threat | Status |
|---|---|---|
| S | CI assumes the deploy role | not reviewed: workflow and trust policy were read only for structure |
| T | State tampering | not reviewed (backend config is an example file) |
| I | RDS, S3, SQS exposure | ok in code: private RDS, public-access block, encryption on |
| I | EKS API reachable from anywhere | gap S-10 (default `0.0.0.0/0`, IAM-authenticated) |
| D | Cost runaway | partial: budgets and tagging modules exist; nothing was applied |
| E | IAM wildcards | `ecr:GetAuthorizationToken` on `*` is required by AWS; no other wildcard seen in a grep |
| | Nothing was planned or applied; `terraform validate` was not run | not reviewed |

### Frontend (nginx + SPA)

| | Threat | Status |
|---|---|---|
| T/I | XSS | partial: CSP without `unsafe-inline` for scripts (`default.conf.template`); asserted by `test_headers_and_errors.py`; the SPA source was not reviewed |
| T | Clickjacking | ok: `X-Frame-Options DENY`, `frame-ancestors 'none'` |
| I | Sniffing, referrer | ok: `nosniff`, `Referrer-Policy` |
| I | Downgrade | gap S-09: no HSTS |
| I | Token storage in the browser | not reviewed |
| D | `/metrics` exposed through the proxy | ok: not proxied (asserted) |

## Residual risk in one paragraph

The authenticated API surface is well covered; the weak points are the places where a feature
was added beside the old identity model rather than through it: live sessions and WebSockets
(S-02, S-03), the unadopted tenancy layer (S-05) and the unauthenticated MQTT adapter (S-04),
plus the missing body cap on the newest `/api/v2` families (S-01).

# UrbanFlow API v3 reference

Generated from `shared/schemas/v3/openapi.v3.snapshot.json` (the contract the tests pin). Every route needs the
infrastructure API key at the gateway and a signed-in user or a personal access token (`Authorization: Bearer`);
the scope column is what a token needs (browser sessions hold every scope). Another user's resource is always a 404.
Errors use the envelope `{"error": {"code", "message", "details"}}`; quota refusals name the quota.

| Method | Path | Scope | Summary |
| --- | --- | --- | --- |
| GET | `/api/v3/capabilities` | experiments:read | Capabilities |
| GET | `/api/v3/copilot/catalogue` | experiments:read | Get Catalogue |
| POST | `/api/v3/copilot/experiments/{experiment_id}/interpretation` | experiments:read | Interpret |
| POST | `/api/v3/copilot/proposals` | experiments:read | Create Proposal |
| GET | `/api/v3/copilot/proposals/{proposal_id}` | experiments:read | Get Proposal |
| POST | `/api/v3/copilot/proposals/{proposal_id}/confirm` | experiments:run | Confirm |
| POST | `/api/v3/copilot/proposals/{proposal_id}/suggestions/{code}` | experiments:read | Apply Suggestion |
| POST | `/api/v3/discovery/estimate` | experiments:read | Estimate |
| GET | `/api/v3/discovery/searches` | experiments:read | List Searches |
| POST | `/api/v3/discovery/searches` | experiments:run | Submit |
| GET | `/api/v3/discovery/searches/{search_id}` | experiments:read | Status |
| POST | `/api/v3/discovery/searches/{search_id}/cancel` | experiments:run | Cancel |
| GET | `/api/v3/discovery/searches/{search_id}/package` | packages:read | Package |
| GET | `/api/v3/discovery/searches/{search_id}/result` | experiments:read | Result |
| GET | `/api/v3/experiments` | experiments:read | List Experiments |
| POST | `/api/v3/experiments` | experiments:run | Submit |
| POST | `/api/v3/experiments/validate` | experiments:read | Validate |
| DELETE | `/api/v3/experiments/{experiment_id}` | experiments:run | Delete |
| GET | `/api/v3/experiments/{experiment_id}` | experiments:read | Status |
| POST | `/api/v3/experiments/{experiment_id}/cancel` | experiments:run | Cancel |
| GET | `/api/v3/experiments/{experiment_id}/package` | packages:read | Export Package |
| GET | `/api/v3/experiments/{experiment_id}/result` | experiments:read | Result |
| POST | `/api/v3/experiments/{experiment_id}/resume` | experiments:run | Resume |
| POST | `/api/v3/packages/verify` | packages:write | Verify Package |
| POST | `/api/v3/stress/breakpoints` | experiments:run | Breakpoints |
| GET | `/api/v3/stress/catalogue` | experiments:read | Catalogue |
| GET | `/api/v3/stress/jobs` | experiments:read | Jobs |
| GET | `/api/v3/stress/jobs/{job_id}` | experiments:read | Status |
| POST | `/api/v3/stress/jobs/{job_id}/cancel` | experiments:run | Cancel |
| GET | `/api/v3/stress/jobs/{job_id}/result` | experiments:read | Result |
| POST | `/api/v3/stress/suites` | experiments:run | Suite |
| GET | `/api/v3/tokens` | tokens:read | List active personal access tokens |
| POST | `/api/v3/tokens` | browser session | Create a personal access token |
| DELETE | `/api/v3/tokens/{token_id}` | tokens:manage | Revoke a personal access token |

Clients: the Python SDK in `sdk/python` covers every route except `POST /api/v3/tokens` (browser only).

# urbanflow-client

Python client and command line for the UrbanFlow V3 API: robustness experiments, `.ufpkg` packages and
personal access tokens. Standard library only (Python 3.11+).

```bash
pip install ./sdk/python
export URBANFLOW_URL=https://urbanflow.example
export URBANFLOW_TOKEN=uf_pat_...        # created in the web app; shown once
```

## Personal access tokens

A token is created in a signed-in browser session (`POST /api/v3/tokens`); this client cannot create one.
Give it only the scopes it needs:

| Scope | Allows |
| --- | --- |
| `experiments:read` | capabilities, validate, list, status, result |
| `experiments:run` | submit, cancel, resume, delete |
| `packages:read` | export a package |
| `packages:write` | verify an uploaded package |
| `tokens:read` / `tokens:manage` | list / revoke your own tokens |

Tokens expire (1-90 days), can be revoked at once, and are limited to 60 requests per minute each.

## Use

```python
import os
from urbanflow_client import Client, QuotaExceeded, InvalidRequest

api = Client(os.environ["URBANFLOW_URL"], os.environ["URBANFLOW_TOKEN"])

print(api.capabilities()["quotas"])
check = api.validate(experiment)             # no work is done
result = api.run(experiment, on_progress=lambda s: print(s["status"]))

experiment_id = api.list_experiments()["experiments"][0]["id"]
api.cancel(experiment_id)                    # later: api.resume(experiment_id)
api.export_package(experiment_id, "run.ufpkg")   # refuses to overwrite
report = api.verify_package("run.ufpkg")
assert report["internallyConsistent"]        # integrity, not authenticity
```

`wait()` raises `WaitTimeout` without cancelling the experiment. Errors are typed: `AuthenticationError`
(401), `PermissionDenied` (403, missing scope), `NotFound` (404, also for someone else's experiment),
`Conflict` (409), `PayloadTooLarge` (413), `InvalidRequest` (422, `.errors` lists every problem),
`QuotaExceeded` (429, `.retry_after`), `ServerError`, plus `TransportError` / `RequestTimeout`.
Only reads are retried (429/502/503/504, honouring `Retry-After`).

## CLI

```bash
python -m urbanflow_client capabilities
python -m urbanflow_client run experiment.json > result.json
python -m urbanflow_client export <id> run.ufpkg
python -m urbanflow_client verify run.ufpkg      # exit 1 if not consistent
python -m urbanflow_client tokens list
```

The URL and token come from the environment only, so a token never lands in shell history. Exit codes:
0 ok, 1 the server refused or failed, 2 bad usage or configuration.

## Security notes

* Credentials never appear in `repr()`, logs, exceptions or pickles, and are only sent over HTTPS (plain HTTP
  only to `localhost`/loopback, or with `allow_insecure=True`).
* Redirects are refused, so the `Authorization` header cannot be forwarded elsewhere.
* Reply and upload sizes are capped (64 MiB reply by default, 10 MiB package).
* The shared infrastructure API key is not something to ship in a distributed tool. `api_key=` /
  `URBANFLOW_API_KEY` exists only for trusted callers inside the private network; how an external SDK reaches a
  locked-down server is an open deployment decision (see the W7 plan).
* A verified package is internally consistent; it does not say who made it.

## Development

```bash
cd sdk/python
python -m pytest tests                    # unit tests, fake transport
cd ../../backend && python -m pytest tests/sdk   # against the real app, and the OpenAPI snapshot
```

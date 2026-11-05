# urbanflow-client — Official Python SDK & CLI

Official standard-library Python client and command-line interface for the UrbanFlow V3 API: robustness experiments, `.ufpkg` portable packages, AI Copilot, AI Strategy Discovery Lab, Strategy Breakpoint Explorer, and Personal Access Tokens (PATs). Requires Python 3.11+ with zero external runtime dependencies.

```bash
pip install ./sdk/python
export URBANFLOW_URL=https://urbanflow.example.com
export URBANFLOW_TOKEN=uf_pat_...        # Generated in the web app under Settings > Tokens
```

---

## Capabilities & Client API

### 1. Robustness Lab Experiments & Packages
```python
import os
from urbanflow_client import Client

api = Client(os.environ["URBANFLOW_URL"], os.environ["URBANFLOW_TOKEN"])

# Inspect server capabilities, supported factor kinds, and tenant quotas
caps = api.capabilities()
print("Quotas:", caps["quotas"])

# Validate experiment specification without consuming compute
check = api.validate(experiment_spec)
assert check["valid"]

# Submit and track experiment with live progress callback
result = api.run(experiment_spec, on_progress=lambda s: print(f"Progress: {s.get('progress')}%"))

# Export self-contained portable package with SHA-256 manifest
api.export_package(result["id"], "experiment.ufpkg")

# Verify local package integrity
report = api.verify_package("experiment.ufpkg")
assert report["internallyConsistent"]
```

### 2. AI Experiment Copilot
```python
# Ingest natural language research queries and get validated experiment proposals
catalogue = api.copilot_catalogue()
proposal = api.propose("What happens if heavy trucks increase by 30% during evening peak?")

# Apply modification suggestions and confirm into a runnable experiment
confirmed = api.confirm_proposal(proposal)
print("Confirmed experiment ID:", confirmed["experimentId"])

# Request evidence-grounded non-hallucinating narrative interpretation of results
interpretation = api.interpret(confirmed["experimentId"])
print(interpretation["summaryMarkdown"])
```

### 3. AI Strategy Discovery Lab (NSGA-II)
```python
# Estimate compute steps for evolutionary multi-objective signal timing search
search_spec = {
    "networkId": "corridor-2j",
    "populationSize": 20,
    "generations": 10,
    "objectives": ["delay", "stops", "emissions"]
}
estimate = api.estimate_search(search_spec)

# Launch asynchronous search job and poll Pareto frontier
job = api.start_search(search_spec)
status = api.search_status(job["id"])
result = api.search_result(job["id"])
print("Non-dominated strategies:", result["paretoFrontier"])
```

### 4. Strategy Breakpoint & Traffic Chaos Explorer
```python
# Explore operational saturation limits under escalating demand ladders
stress_profile = api.stress_catalogue()["profiles"][0]
job = api.start_breakpoints({"scenarioId": "junction-4arm", "profile": stress_profile})
breakpoint_result = api.stress_result(job["id"])
print("Breakdown Arrival Rate:", breakpoint_result["breakdownArrivalRate"])
```

### 5. Insights & Analytics
```python
# Comparative analytics across paired strategies
comp = api.comparison(scenario_id="corridor-2j")
print("Delay delta:", comp["delayDelta"])

# Sobol multi-factor variance sensitivity analysis
sens = api.sensitivity(experiment_id="exp-123")
print("First-order indices:", sens["firstOrder"])

# Check latest k6 performance load-test reports
loadtest = api.loadtest_latest()
print(f"p95 Latency: {loadtest['p95LatencyMs']} ms")

# Query benchmark comparisons between trained RL policies and baselines
rl_eval = api.rl_comparison("ppo-vs-fixed-time")
```

### 6. Personal Access Token (PAT) Management
```python
# List active access tokens and revoke compromise
tokens = api.list_tokens()
api.revoke_token(tokens[0]["id"])
```

---

## Command Line Interface (CLI)

```bash
# Query server capabilities and quotas
python -m urbanflow_client capabilities

# Submit experiment JSON and stream result to stdout
python -m urbanflow_client run experiment.json > result.json

# Export experiment to .ufpkg package
python -m urbanflow_client export <experiment-id> run.ufpkg

# Verify package integrity offline
python -m urbanflow_client verify run.ufpkg

# List active personal access tokens
python -m urbanflow_client tokens list
```

---

## Security & Error Handling

- **Zero Credential Leakage:** Sensitive tokens never appear in `repr()`, stack traces, exception messages, or log records.
- **Strict HTTPS Enforcement:** Plain HTTP is refused for non-loopback addresses unless `allow_insecure=True` is explicitly passed.
- **Typed Error Hierarchy:**
  - `AuthenticationError` (HTTP 401)
  - `PermissionDenied` (HTTP 403: missing capability scope)
  - `NotFound` (HTTP 404: unknown ID or resource owned by another tenant)
  - `PayloadTooLarge` (HTTP 413: payload exceeds 1 MiB / 10 MiB limits)
  - `InvalidRequest` (HTTP 422: `.errors` contains structured validation failures)
  - `QuotaExceeded` (HTTP 429: `.retry_after` seconds to wait)
  - `WaitTimeout`, `TransportError`, `RequestTimeout`
- **Safe Retries:** Automatic idempotent read retries with exponential backoff on HTTP 429, 502, 503, 504 honoring `Retry-After`. Mutating requests are never retried automatically.

---

## Development & Test Execution

```bash
cd sdk/python

# Run SDK unit tests against fake transport mocks
python -m pytest tests/

# Run end-to-end integration tests against backend and OpenAPI snapshot
cd ../../backend
python -m pytest tests/sdk/
```

# V3.0 W1 — Security review of `/api/v3` (experiments and capabilities)

> **Status:** Done 2026-10-15 for the W1 slice ([#151](https://github.com/Viraj281105/Traffic-Simulation/issues/151), [#153](https://github.com/Viraj281105/Traffic-Simulation/issues/153)), at commit `9086a9a` plus the fixes listed here. **Scope:** `backend/src/experiments/`, the experiment runner and factor application in `backend/src/uncertainty/`, the worker-pool helper in `backend/src/study/runner.py`, and the mounting and size cap in `backend/src/main.py` / `request_limits.py`. **Method:** reading the code against the threat list below, plus attack probes through the real application (hostile documents, probing ids). This is a developer review, **not an independent penetration test**, and it covers a single-process deployment.
> **Rule it enforces:** ADR-013 — every v3 resource is private to its owner; another user's id is a 404; there is no administrator override.

## 1. What is exposed

Authenticated users submit JSON documents that the server turns into simulations. The new surface is `GET /api/v3/capabilities`, `POST /api/v3/experiments[/validate]`, `GET /api/v3/experiments[/{id}[/result]]` and `DELETE /api/v3/experiments/{id}`. Every route needs the API key (when configured) **and** a signed-in user (`tests/api/test_v3_route_auth.py`, read from the app's own OpenAPI document). No user-supplied code, path, URL or file name is ever executed, opened or fetched: a scenario is data validated by strict models and by the engine's configuration schema, and simulations run in worker processes that know nothing of the request.

## 2. Findings and what was done

| # | Finding | Severity | Evidence before | Fix | Test |
| --- | --- | :-: | --- | --- | --- |
| F1 | **Request CPU spent before the limit was checked.** `prepare` resolved (validated) every alternative and only then compared their number with the limit of 6. A body of 1 MiB holds about 20 000 alternatives | High (any signed-in user can occupy a server thread and, through the GIL, slow every request) | 300 alternatives: 3.0 s; 20 000 alternatives: **70.3 s** before the refusal | The count is checked before any alternative is resolved; the request model also caps the list at 64 while parsing | 20 000 alternatives refused in **0.08 s** (`test_a_huge_alternatives_list_is_refused_before_any_is_validated`) |
| F2 | **Hostile nesting gave a 500.** A merge patch or `advanced` section nested 3 000 levels deep raised `RecursionError` inside the merge | Medium (an unhandled error path, and a way to burn CPU) | HTTP 500 | The document depth is measured iteratively first and refused above 24 levels with a readable message; real documents nest about 8 | `test_deeply_nested_documents_are_refused_not_a_500` (patch, `advanced`, scenario) |
| F3 | **The work quota counted seconds, not engine steps.** The configuration contract allows a time step of 0.05 s, which costs twice as much for the same simulated seconds; `advanced` can also change the step | Medium (quota bypass by a factor of two) | 60 runs of 3 600 s were allowed at both steps | The quota is now `maxSimulationStepsPerExperiment` (2 500 000 = 250 000 s at 0.1 s), computed from the **compiled** configuration of every alternative (the step may come from `advanced`) | `test_a_smaller_time_step_costs_more_even_for_the_same_seconds`, `test_an_advanced_time_step_override_is_counted` |
| F4 | **An unbounded string was echoed back.** `baseline` had no length limit and appears in the error message | Low | A 500 000-character baseline came back in the response | `baseline` is limited to 32 characters (an alternative id) | `test_the_baseline_id_is_length_bounded` |
| F5 | **Raw exception text was stored and returned.** A failed experiment's `error` was `str(exc)`, which for an engine or operating-system error can contain file paths | Low (only the owner sees it) | Message of an `OSError` shown verbatim | Unexpected errors read `The experiment failed while running (<Type>). The server log has the details.`; only our own refusal types keep their message | `test_an_unexpected_error_shows_its_type_not_its_message` |
| F6 | **Scale factors could describe a different junction.** A scale factor needed only a positive lower bound, so `[1, 1e300]` was legal and produced nothing but excluded conditions | Low (wasted compute, numeric edge cases) | Accepted | Scale factors must stay within [0.05, 10] | `test_scale_factor_bounds_are_limited` |

## 3. Checked and found sound

| Threat | How it is handled | Evidence |
| --- | --- | --- |
| **Access to another user's experiment** (read, result, delete, list) | `store.get` returns the record only to its owner; an unknown id and someone else's id give byte-identical 404 bodies; the list query filters on the owner in SQL; there is no admin dependency on the router | `test_another_users_experiment_is_a_404_everywhere`, `test_ids_are_unguessable_and_probing_gives_no_information`, persistence test after a reload |
| **Guessing ids** | ids are random UUIDs (`uuid4().hex`), not counters; SQL-looking, 5 000-character and traversal ids all give the same 404 | `test_ids_are_unguessable…`, probes |
| **SQL injection** | every statement uses bound parameters; the only interpolated text is constants | code review of `ExperimentStore` |
| **Mass assignment** | records are built server-side from the validated request; the client cannot set owner, status, result or fingerprints; the request model rejects unknown fields by name (`extra="forbid"`) | `test_invalid_requests_are_422_with_every_problem_named` |
| **Oversized bodies** | `/api/v3/experiments` is under the 1 MiB body cap (413 in the standard error envelope), including `/validate` | `test_oversized_experiment_body_is_413` |
| **Running too much at once** | one running experiment per user, two server-wide, 50 stored per user (429, quota named); the check and the reservation happen under one lock, so two simultaneous submissions cannot both pass a limit of one | `test_one_running_experiment_per_user_and_a_server_wide_cap`, `test_stored_experiments_per_user_are_capped…` |
| **Quotas on the size of one experiment** | 6 alternatives, 2 000 runs, 2 500 000 engine steps (422, quota named) | `test_too_many_runs…`, `test_too_much_simulated_work…`, `test_too_many_alternatives…` |
| **Persistence failure** | a database error never fails an experiment (kept in memory); a failed delete is raised, not hidden | `test_a_broken_database_never_fails_an_experiment` |
| **Restart** | an experiment a dead process was running reads `failed` with an explanation; it is not left "running" and does not hold a slot | `test_an_experiment_a_dead_process_was_running_is_reported_failed` |
| **Migration risk** | `uf_experiments` is created with `CREATE TABLE IF NOT EXISTS`; nothing existing is altered; running it twice changes nothing; rows already written survive | `test_migration_is_additive_and_idempotent`, `test_migration_keeps_rows_already_written` |
| **Stored XSS** | free text (name, rationale, labels) is returned as JSON strings and rendered by React as text; nothing is injected as HTML; the page uses no `dangerouslySetInnerHTML` | code review of `ExperimentResultView` |
| **CSRF** | authentication is a bearer token in a header, not a cookie, so a foreign page cannot make the browser attach it | design |
| **Code or file inclusion** | no user input reaches a file path, a URL, `eval`, a subprocess or a pickle; `advanced` is merged into the engine configuration and then validated by the configuration schema and semantic checks | code review of `apply.py`, `runner.py`, `scenario.py` |
| **Hostile numbers** | NaN and infinity are rejected in the specification; demand above the arm limit is excluded and counted, never clipped; `timeStep` below the engine's step budget is refused by the existing configuration check | `test_non_finite_numbers_are_rejected`, probes |
| **Information in responses** | results carry the commit hash and Python version (as the V2.0 planner does); error bodies use the standard envelope with no stack traces | review |

## 4. Residual risks and limitations (accepted for now, written down)

1. **Single process.** Quotas and the "running" count live in the memory of one uvicorn process; with several workers each would count separately, and a worker starting up would mark experiments of another worker as interrupted. The same is true of `/api/v2/planning`. A shared quota store is required before scaling out (ADR-013, Future considerations).
2. **No per-user rate limit on `POST /experiments/validate`.** It is cheap now that the document is bounded (a few milliseconds for 6 alternatives) but it is not metered, as `/api/v2/planning/validate` is not. Add a rate limit with the personal-access-token work (W7).
3. **Preparation runs in the API process.** Building the scenarios of an experiment is Python work in a background thread of the API process: 240 runs took 1.75 s (measured), so the largest allowed experiment (2 000 runs) would take roughly 15 s (extrapolated, not measured). Simulation itself runs in worker processes.
4. **Extreme JSON nesting at the framework level.** The document-depth check runs after the body is parsed. A body nested deep enough to fail inside Python's own JSON parser is outside this module (it affects every endpoint of the application) and is bounded only by the 1 MiB body cap.
5. **Quota figures are proposals.** The step budget comes from one measurement on one machine; it is *unverified* elsewhere.
6. **No cancellation.** A running experiment cannot be stopped or deleted (409). Cancel/resume is scheduled for W7.
7. **No audit log or personal access tokens yet** (W7). Until then, the sign-in session is the only credential.
8. **Fixed (2026-10-15): `/api/v2/planning` had finding F2.** A merge patch or `advanced` section nested 3 000 levels deep returned **HTTP 500** on `validate`, `run` and `jobs` too. It did *not* have F1: the V2.0 model enforces its limit of 6 alternatives while parsing, before anything is resolved. `parse_study` now measures the depth first, with the same iterative helper as `/api/v3` (`src/core/limits.py`, shared, limit 24), and refuses a deeper study with HTTP 422 and the message "The document is nested more than 24 levels deep". Only the failure mode changed: no successful response and no existing test did. Regression tests: `backend/tests/planning/test_planning_depth.py` (patch and `advanced`, on all three routes, through the real app).

## 5. How to re-run the review

```bash
cd backend && python -m pytest tests/experiments/test_security.py tests/api/test_v3_route_auth.py -q
```

The attack probes are the tests named above; each one fails if its fix is removed (checked by deleting the depth check and the alternatives check and watching them fail).

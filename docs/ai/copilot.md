# Experiment Copilot (V3.0 W5)

The Copilot turns a research question into a **proposed** Robustness Lab experiment, which the backend
validates and which runs only after the user confirms it. It can also read a finished experiment's
measured results back in plain language. It implements strategy §15.1 with the limits stated below.

## Architecture

```
question (≤ 2,000 chars)
  ├─ model proposer (when a provider is configured, switched on and within budget)
  └─ rule-based proposer (always available; the fallback; not called AI)
        ▼
ExperimentIntent  — bounded enums and numbers only (alternatives, baseline, aggression, demand,
                    uneven demand, vehicle mix, study size, replications, primary indicator)
        ▼ deterministic builder (src/copilot/proposer.py)
urbanflow-experiment document
        ▼ validation boundary (src/copilot/validation.py): the same prepare() as POST /api/v3/experiments,
          plus the daily simulated-seconds quota; coded issues and deterministic suggestions
ExperimentProposal (urbanflow-experiment-proposal v1): validated, issues, contentHash, provenance
        ▼ user inspects; POST …/confirm with the content hash (single use, creator only)
ordinary experiment submission (auth, ownership, quotas, limits)
        ▼ completed result
evidence object ─► template summary (always) ─► model text (optional) ─► grounding check
```

A model **never writes the experiment**. It fills the small intent document; anything outside it (for
example an injected `"experiment"` field) makes the answer invalid, it is sent back with the validation
error at most twice, and then the rule-based proposer is used. Every confirmable proposal has passed
backend validation (criterion C1).

## API (`/api/v3/copilot`, scopes in brackets)

| Route | Purpose |
| --- | --- |
| `GET /catalogue` [`experiments:read`] | What may be proposed: alternatives, profiles, demand levels, bounds, quotas (hashed into every proposal) |
| `POST /proposals` [`experiments:read`] | `{question, mode: "auto" \| "deterministic"}` → proposal (runs nothing) |
| `GET /proposals/{id}` [`experiments:read`] | The caller's proposal (404 for anyone else's) |
| `POST /proposals/{id}/suggestions/{code}` [`experiments:read`] | A **new** proposal with one validation suggestion applied, validated again (never a silent repair) |
| `POST /proposals/{id}/confirm` [`experiments:run`] | `{contentHash}` → submits the experiment once; 409 if invalid, already confirmed or the hash differs |
| `POST /experiments/{id}/interpretation` [`experiments:read`] | `{preferred?, mode}` → measured evidence, template summary, unfavourable findings, and a model text only if it passes grounding |

Proposals live 30 minutes in memory (at most 50 per user). The SDK has matching methods
(`propose`, `apply_suggestion`, `confirm_proposal`, `interpret`).

## Interpretation and grounding

The summariser receives only the caller's own result, reduced to an evidence object (counts, eligibility
class, per-alternative means, preference shares, win/tie/loss and mean differences with intervals,
real-world validity, limitations). The template summary is built from it with every number written
exactly as the evidence holds it. A model text is kept only if **every numeral** in it is a number of the
evidence (a proportion may appear as a percentage); otherwise it is suppressed and the template is shown.
The mandatory sections (eligibility, N conditions / r replications / total runs, real-world validity,
limitations, and every unfavourable finding for the preferred alternative) are appended deterministically
whatever the model wrote (C5, C6).

## Security and cost controls

* The model has no tools and no network or file access; it sees the question, the catalogue and, for
  interpretations, the caller's evidence object. The provider key (`GROQ_API_KEY`) is server-side only.
* Kill switch `AI_COPILOT_ENABLED=0`; model-call caps `AI_CALLS_PER_CLIENT_PER_DAY` (default 60) and
  `AI_CALLS_PER_DAY` (default 1,000) shared with the dashboard assistant; per-user caps
  `COPILOT_PROPOSALS_PER_DAY` and `COPILOT_INTERPRETATIONS_PER_DAY` (default 100 each, 429 when exceeded).
* Prompt and output payloads are not logged; failures are logged without content.
* Confirmation is bound to the creator and the content hash, single use, and re-checks the hash.

## Evaluation (`copilot-eval-v1`)

`src/copilot/eval/copilot-eval-v1.json`: 40 questions (30 in-scope of which 10 held out, 5 ambiguous,
5 adversarial) with expert checklists. `python -m src.copilot.evaluation` scores a proposer.

Rule-based baseline (measured 2026-10-26): all 30 in-scope proposals validate; key-element recall 0.98 on
the 20 development items and 0.95 on the 10 held-out items; all ambiguous items state their assumptions;
all adversarial items are flagged and none can run without confirmation. **Caveat:** the rule-based
proposer and the evaluation set were written in the same session by the same author, so this baseline is
optimistic; an independently written set should replace it before any claim is made.

**AI claim status: not made.** C3 requires the model to beat the baseline by 15 percentage points on the
held-out set, which is not possible against a 0.95 baseline, and no provider evaluation has been run
(decision D-AI1). Capabilities therefore report `experimentCopilot: true` (the assistant exists) and
`aiCopilot: false`. The UI labels rule-based proposals as such and model-assisted ones as
"AI-assisted proposal — validated by the backend; you confirm it".

## Limitations

The intent covers one four-arm, one-lane-per-arm junction family with preset demand levels; questions about
other geometries are mapped onto it and the assumption is stated. Estimated wall time is not given
("unverified"). A language model's reading of results can be wrong; the measured tables are the evidence.

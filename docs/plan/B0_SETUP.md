# B0 – Decisions and setup (Oct 28 – Oct 30, 2026)

Prep week before W31. No feature code. Two outputs: who owns which part of the repo, and the open decisions with an owner and a deadline each. Proposed for review; nothing here is agreed until both people sign off.

## 1. Repo ownership (proposed)

Rule: one owner per directory so merges do not collide. A change in someone else's directory needs their review.

| Path | Owner | Notes |
| --- | --- | --- |
| `backend/src/engine`, `controllers`, `intersection`, `vehicles`, `roads`, `networks`, `core` | Viraj | Simulation core; network model (F5) lands in `networks` |
| `backend/src/metrics`, `uncertainty`, `study`, `experiments`, `calibration`, `stress` | Viraj | Statistics, metrics, calibration |
| `backend/src/copilot`, `ai`, `strategies`, `suites` | Viraj | Copilot, eval harness (F4) |
| New: `backend/src/rl/`, `pipelines/rl/` | Khushi | Gymnasium environment, DQN and PPO training, MLflow tracking, model registry, RL evaluation (F18) |
| `backend/src/api`, `database`, `access.py`, `history`, `replays`, `live` | Viraj | Backend, run store, auth |
| `backend/tests` | Viraj | Khushi adds tests for report and analytics code only |
| `frontend/` | Khushi | UI, dashboards, report views |
| `frontend/src` network map viewer, congestion heatmap, network metric views, canvas markers | Viraj | Simulation-facing UI (F5, F13); Khushi reviews |
| `backend/src/planning`, `scenario`, `snapshot` (report and analytics output only) | Khushi, by agreement | Review each other's changes |
| `sdk/`, `shared/` | Both | Contract changes need both reviews |
| New: `services/go/` (F1), `infra/` (Terraform, Helm, F2/F3), `pipelines/` (Airflow, dbt, F3/F7) | Viraj | Create when the first feature needs them |
| New: `docs/plan/`, `docs/decisions/` | Both | ADRs written by the feature owner |
| `.github/` | Both | CI changes announced before merge |

Open points on this table:
- `.github/CODEOWNERS` now covers `services/`, `infra/`, `pipelines/` and the RL paths. Still missing: the other `backend/src/*` subfolders, `sdk/`, and the frontend map-viewer paths. Add them once this table is agreed.
- It also lists `/backend/` as Viraj only; Khushi's report and analytics code in backend needs an exception line.

## 2. Decisions

| # | Decision | Owner | Needed by | Blocks | Status |
| --- | --- | --- | --- | --- | --- |
| 1 | AWS account, who owns it, monthly budget cap | Viraj | W35 (Dec 4) | F2, F7, F17 | Open |
| 2 | Calibration city and open count datasets | Khushi | before W39 (Dec 28) | F11, F14, gate G-CAL | Open |
| 3 | Exam and leave weeks for both people | Both | Oct 30 | Re-plan slack weeks | Open |
| 4 | Live traffic feed source for the twin | Both | W46 (Feb 19) | F14 | Open |
| 5 | Hardware for the signal-head demo (Pi / ESP32) | Viraj | W46 (Feb 19) | F19 | Open |

### 2.1 AWS (decision 1)

Questions to answer: whose account; a budget alert and hard cap in rupees or dollars; which region; free tier or paid; who holds root credentials. Until answered, F2 and F7 use local stand-ins (MinIO for S3, kind for the cluster), as the plan allows.

### 2.2 Calibration data (decision 2)

Shortlist 3 cities with open traffic counts. For each, record: data licence, count granularity (per minute or per hour), whether junction-level turning counts exist, and OSM road quality. Pick one by W38. G-CAL in W41 needs real counts to compare against.

### 2.3 Exams and leave (decision 3)

List dates for both people. The slack weeks are W45, W53, W59; move them if leave overlaps. W40 is already reduced because of the V3.0 showcase on Jan 7.

## 3. Done when

- [ ] Ownership table agreed and `.github/CODEOWNERS` updated
- [ ] AWS owner and cap recorded in Decision 1
- [ ] Calibration shortlist written up (Khushi)
- [ ] Exam and leave dates added; slack weeks re-checked
- [ ] Row B0 in `WEEKLY_PLAN.md` set to DONE

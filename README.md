# Traffic Intersection Control Comparison

> A comparative traffic simulation framework for evaluating **Fixed-Time Signal Control** vs. **Modern Roundabout Control** using multiple performance metrics.

## Overview

This project simulates and compares two intersection control strategies to determine which performs better under various traffic conditions. The simulation uses the **Intelligent Driver Model (IDM)** for vehicle physics and computes **10 performance metrics** across 5 categories.

### Control Strategies

| Strategy | Description |
|----------|-------------|
| **Fixed-Time Traffic Signal** | Traditional signal-controlled intersection with fixed green/yellow/red phase cycles |
| **Modern Roundabout** | Yield-at-entry circular intersection with gap acceptance behavior |

## Architecture

The project is organized as a monorepo with strict separation between Backend (Simulation Engine) and Frontend (Visualization Dashboard). Both communicate through shared data contracts.

```
├── backend/       → Simulation engine, metrics, API (Python + FastAPI)
├── frontend/      → Dashboard, visualization, charts (React + TypeScript + Vite)
├── shared/        → Data contracts, schemas, types (JSON Schema)
├── docs/          → Architecture specifications and project documentation
├── scripts/       → Development automation
└── examples/      → Sample configurations and outputs
```

See the [Architecture Documents](docs/architecture/) for detailed specifications.

## Architecture Documents

| # | Document | Description |
|---|----------|-------------|
| 01 | [Repository Architecture](docs/architecture/01-repository-architecture.md) | Folder structure, ownership boundaries |
| 02 | [Backend Architecture](docs/architecture/02-backend-architecture.md) | Simulation engine module design |
| 03 | [Frontend Architecture](docs/architecture/03-frontend-architecture.md) | React dashboard design |
| 04 | [Shared Contract Layer](docs/architecture/04-shared-contract-layer.md) | Contract ownership and versioning |
| 05 | [Snapshot Contract](docs/architecture/05-snapshot-contract.md) | Real-time simulation state schema |
| 06 | [Scenario Configuration](docs/architecture/06-scenario-configuration-contract.md) | Simulation configuration schema |
| 07 | [Metric Contract](docs/architecture/07-metric-contract.md) | 10 metrics with mathematical definitions |
| 08 | [Communication Contract](docs/architecture/08-communication-contract.md) | REST + WebSocket API design |
| 09 | [Engineering Standards](docs/architecture/09-engineering-standards.md) | Naming, Git workflow, code quality |
| 10 | [Repository Bootstrap](docs/architecture/10-repository-bootstrap.md) | Labels, milestones, initial issues |


## Project Planning & Decisions

In addition to system specifications, the repository maintains planning, workflow, and decision history:

| Component | Directory | Description |
|-----------|-----------|-------------|
| **Architecture Decisions** | [docs/decisions/](docs/decisions/) | The Architecture Decision Record (ADR) library tracking historic context. |
| **Kanban & Roadmap** | [docs/project-management/](docs/project-management/) | Milestones roadmap, label systems, and board configurations. |
| **GitHub Issues** | [docs/issues/](docs/issues/) | 61 deconstructed atomic engineering tasks partitioned by implementation phase. |

## Performance Metrics

| Category | Metrics |
|----------|---------|
| **Operational Efficiency** | Average Wait Time, Throughput, Queue Length Statistics |
| **Traffic Flow Quality** | Stop Count, Speed Variance Index, Travel Time Reliability |
| **System Performance** | Idle Opportunity Loss, Critical Saturation Volume |
| **Fairness** | Directional Fairness Index |
| **Physical Constraints** | Space / Footprint Consumed |

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- npm 9+

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
python -m src.main
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Team

| Developer | Scope |
|-----------|-------|
| Viraj Jadhao | Backend — Simulation Engine, Physics, Metrics, API |
| Khushi Kashyap | Frontend — Dashboard, Canvas, Charts, Playback |

## Contributing

See [Engineering Standards](docs/architecture/09-engineering-standards.md) for naming conventions, commit message format, branch strategy, and code quality requirements.

## License

MIT License

# Traffic Intersection Control Comparison

> A comparative traffic simulation framework for evaluating **Fixed-Time Signal Control** vs. **Modern Roundabout Control** using multiple performance metrics.

## Overview

This project simulates and compares two intersection control strategies to determine which performs better under various traffic conditions. The simulation uses the **Intelligent Driver Model (IDM)** for vehicle physics and computes **10 performance metrics** across 5 categories.

### Control Strategies

| Strategy                      | Description                                                                         |
| ----------------------------- | ----------------------------------------------------------------------------------- |
| **Fixed-Time Traffic Signal** | Traditional signal-controlled intersection with fixed green/yellow/red phase cycles |
| **Modern Roundabout**         | Yield-at-entry circular intersection with gap acceptance behavior                   |

## Architecture

The project is organized as a monorepo with strict separation between Backend (Simulation Engine) and Frontend (Visualization Dashboard). Both communicate through shared data contracts.

```
├── [backend/](backend/README.md)       → Simulation engine, metrics, API, SQLite (Python + FastAPI)
├── [frontend/](frontend/README.md)      → Landing page and simulation dashboard (React + TypeScript + Vite)
├── [shared/](shared/README.md)        → JSON Schema contracts
├── docs/          → Runtime operations, architecture, decisions, deployment, and planning
└── [scripts/](scripts/README.md)       → Study, schema, and GitHub automation
```

See the [Operations and API guide](docs/operations.md) for current behavior. Architecture documents describe the checked-in implementation; ADRs and issue files may preserve historical planning context.

## Architecture Documents

| #   | Document                                                                          | Description                              |
| --- | --------------------------------------------------------------------------------- | ---------------------------------------- |
| 01  | [Repository Architecture](docs/architecture/01-repository-architecture.md)        | Folder structure, ownership boundaries   |
| 02  | [Backend Architecture](docs/architecture/02-backend-architecture.md)              | Simulation engine module design          |
| 03  | [Frontend Architecture](docs/architecture/03-frontend-architecture.md)            | React dashboard design                   |
| 04  | [Shared Contract Layer](docs/architecture/04-shared-contract-layer.md)            | Contract ownership and versioning        |
| 05  | [Snapshot Contract](docs/architecture/05-snapshot-contract.md)                    | Real-time simulation state schema        |
| 06  | [Scenario Configuration](docs/architecture/06-scenario-configuration-contract.md) | Simulation configuration schema          |
| 07  | [Metric Contract](docs/architecture/07-metric-contract.md)                        | Current metric keys and implementation ownership |
| 08  | [Communication Contract](docs/architecture/08-communication-contract.md)          | REST + WebSocket API design              |
| 09  | [Engineering Standards](docs/architecture/09-engineering-standards.md)            | Naming, Git workflow, code quality       |
| 10  | [Repository Bootstrap](docs/architecture/10-repository-bootstrap.md)              | Labels, milestones, initial issues       |

## Project Planning & Decisions

In addition to system specifications, the repository maintains planning, workflow, and decision history:

| Component                  | Directory                                            | Description                                                                    |
| -------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------ |
| **Architecture Decisions** | [docs/decisions/](docs/decisions/)                   | The Architecture Decision Record (ADR) library tracking historic context.      |
| **Kanban & Roadmap**       | [docs/project-management/](docs/project-management/) | Milestones roadmap, label systems, and board configurations.                   |
| **GitHub Issues**          | [docs/issues/](docs/issues/)                         | 61 deconstructed atomic engineering tasks partitioned by implementation phase. |
| **Future Scope & Roadmap** | [docs/future-scope/](docs/future-scope/)             | Finalized roadmap & Google Maps-grade Digital Twin UI/UX innovation blueprints.|

## Performance Metrics

| Category                      | Metrics                                                                               | Description                                                   |
| ----------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| **Operational Efficiency**    | Average Wait Time, Throughput, Queue Length Statistics                                | Core delay and volume clearing statistics                     |
| **Traffic Flow Quality**      | Stop Count, Speed Variance Index, Travel Time Reliability, Average Travel Speed (ATS) | Vehicle comfort and flow stabilization markers                |
| **System Performance**        | Idle Opportunity Loss, Critical Saturation Volume, Intersection Utilization %         | Capacity and active service metrics                           |
| **Fairness & Stability**      | Directional Fairness Index (DFI), Queue Stability Index (QSI)                         | Variance across approaches and queues                         |
| **Physical Constraints**      | Space / Footprint Consumed                                                            | Land usage footprint comparison                               |
| **Composite (specialist layer)** | **Master Efficiency Score**                                                        | Fixed-weight composite (0–100); shown only in the specialist table, not as a verdict |

The guided comparison presents these as answers to everyday questions (how long drivers wait, how much gets through, how long queues get, whether directions are treated alike, why, and how reliable the result is); every metric above stays available in its "All measurements" layer. See the [UrbanFlow user narrative](docs/product/urbanflow-user-narrative.md).

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose (optional, for containerized run)

### Running via Docker (Recommended)

Run the entire containerized system (FastAPI Simulation Engine + React Dashboard + Nginx Reverse Proxy + Persistent SQLite Data Volume):

```bash
docker compose up --build -d
```

- **Frontend landing page**: [http://localhost](http://localhost) (or [http://localhost:3000](http://localhost:3000))
- **Simulation dashboard**: [http://localhost/app/comparative](http://localhost/app/comparative) — the guided comparison (describe the junction → watch both run → plain-language results with a reliability check). The app has three sections: **Compare** (`/app/comparative`), **Saved** (`/app/history`) and the **Research lab** (`/app/research`, with `/app/volume`, `/app/validation`, `/app/signal`, `/app/roundabout`). Each view has its own URL, so refresh, bookmarks and back/forward work; the old `/app.html` link still redirects. Each saved run has its own page at `/app/runs/<runId>` (configuration, seed, provenance, metrics, notes/tags, exports, re-run), and `/app/compare?runs=<id>,<id>` compares stored runs
- **Backend API**: proxied by nginx at [http://localhost/api](http://localhost/api) (the backend container is not published on its own port); build version at [http://localhost/api/version](http://localhost/api/version)
- **Health Check**: [http://localhost/health](http://localhost/health)

#### Windows: `start.ps1` (Docker only)

`start.ps1` runs the same stack and needs nothing on the host but Docker Desktop and Git — no Python, Node or npm. It starts Docker Desktop if needed, validates `.env` and the Compose file, checks that the host ports are free, rebuilds only the images whose inputs changed (Docker's build cache decides; docs/test edits rebuild nothing), recreates only containers whose image or configuration changed, waits for health, and smoke-tests the result (pages, static assets, `/health`, database, study workers, live WebSocket, and that the running images are the current build).

```powershell
.\start.ps1                    # build what changed, start, verify
.\start.ps1 -Status            # read-only: containers, images, database, source version
.\start.ps1 -Logs [backend]    # follow logs
.\start.ps1 -Restart           # recreate containers from current images (data kept)
.\start.ps1 -Rebuild           # rebuild images without cache
.\start.ps1 -SmokeTest         # re-check the running stack
.\start.ps1 -Clean             # remove containers and images; database volumes are kept
.\start.ps1 -Clean -DeleteData # ...and delete the database volume (asks for confirmation)
.\start.ps1 -Dev               # development stack with hot reload (combines with every switch above)
```

**Development mode (`-Dev`)** runs `docker-compose.dev.yml`: the Vite dev server at [http://localhost:5173](http://localhost:5173/app/comparative) and uvicorn `--reload` at [http://localhost:8000](http://localhost:8000/docs), both in containers with the source bind-mounted, so edits under `frontend/` and `backend/src` apply live. Dependencies stay inside the images (their `dev` build targets), which rebuild only when `requirements.txt` or `package*.json` change. The development sign-in is on (you are "Local developer"), so saving runs works without Cognito. Development has its own database volume (`traffic-simulation_traffic_data_dev`); production and development share one Compose project, so starting one replaces the other.

The database lives in the named volume `traffic-simulation_traffic_data`; nothing but `-Clean -DeleteData` removes it. If port 80 or 3000 is taken, set `URBANFLOW_HTTP_PORT` / `URBANFLOW_ALT_HTTP_PORT` (shell or `.env`). The production image has no development sign-in, so without Cognito configured the app runs signed out; use `-Dev` to work signed in.

To stop the containers:
```bash
docker compose down
```

### Running Natively for Local Development

For hot reload, use `.\start.ps1 -Dev` (or `docker compose -f docker-compose.dev.yml up -d --build`). To run the services natively instead:

- **Manual Backend Setup**:
  ```bash
  cd backend
  python -m venv .venv
  .venv\Scripts\activate          # Windows
  # source .venv/bin/activate     # macOS/Linux
  pip install -r requirements.txt
  uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
  ```
- **Manual Frontend Setup**:
  ```bash
  cd frontend
  npm install
  npm run dev
  ```
  Visit [http://localhost:5173](http://localhost:5173) for the landing page or [http://localhost:5173/app/comparative](http://localhost:5173/app/comparative) for the dashboard.

### AWS Free Tier Cloud Deployment

For deploying the containerized application to an **AWS EC2 Free Tier (`t2.micro` / `t3.micro`)** instance with 2 GB Linux Swap, Nginx reverse proxying, and persistent storage, see:

📖 **[AWS Free Tier Deployment Guide](docs/deployment/AWS_FREE_TIER_DEPLOYMENT.md)**

## Team

| Developer      | Scope                                              |
| -------------- | -------------------------------------------------- |
| Viraj Jadhao   | Backend — Simulation Engine, Physics, Metrics, API |
| Khushi Kashyap | Frontend — Dashboard, Canvas, Charts, Playback     |

## Contributing

See [Engineering Standards](docs/architecture/09-engineering-standards.md) for naming conventions, commit message format, branch strategy, and code quality requirements.

## License

MIT License

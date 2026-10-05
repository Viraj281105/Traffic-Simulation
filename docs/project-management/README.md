# Project Management Specifications

This directory contains **historical** project-management resources: the original phase-based milestone plan, labels, Kanban design and GitHub automation notes. It is not a statement of current implementation status and **not a roadmap**: the single authoritative roadmap is [docs/ROADMAP.md](../ROADMAP.md). For the running system use the [documentation hub](../README.md).

## Directory Index

| Document | Purpose |
|----------|---------|
| **[roadmap.md](roadmap.md)** | Historical phase-0–6 milestone plan used to build V0.x (superseded by [ROADMAP.md](../ROADMAP.md)). |
| **[labels.md](labels.md)** | GitHub labeling configuration used by automation scripts. |
| **[kanban.md](kanban.md)** | Historical Kanban columns and saved-view design. |
| **[github-management-package.md](github-management-package.md)** | GitHub issue, milestone, label, and dependency package. |

## Quick Start: Project Workspace Setup

To configure your GitHub repository workspace with all labels, milestones, and issues defined here:

1.  Provide your Personal Access Token in a `.env` file at the root of the repository:
    ```
    GITHUB_TOKEN=your_pat_token_here
    ```
2.  Run the setup script:
    ```bash
    python scripts/setup_github.py
    ```
3.  The script will auto-detect your git remote URL and automatically populate your repository.
4.  Navigate to GitHub and create a new Project Board matching the guidelines in [kanban.md](kanban.md).

# Project Management Specifications

This directory contains the project management resources, guidelines, and roadmap documentation for the **Traffic Intersection Control Comparison Framework**.

## Directory Index

| Document | Purpose |
|----------|---------|
| **[roadmap.md](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/project-management/roadmap.md)** | The 14-phase development roadmap, from repository setup to final project demonstration. Contains targets, deliverables, and exit gates. |
| **[labels.md](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/project-management/labels.md)** | The complete GitHub labeling system containing 42 prefixes-structured labels. Covers components, priorities, tech, status, and difficulties. |
| **[kanban.md](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/project-management/kanban.md)** | The definition of Kanban columns, WIP limits, automated movement rules, swimlanes, and 8 customized saved views. |
| **[github-management-package.md](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/project-management/github-management-package.md)** | The master reference package. Cross-maps all 61 issues, their numbers, milestones, label assignments, and dependencies into a single table. |

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
4.  Navigate to GitHub and create a new Project Board matching the guidelines in [kanban.md](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/project-management/kanban.md).

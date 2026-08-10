# GitHub Labeling System Specification

This document defines the official GitHub labeling system for the **Traffic Intersection Control Comparison Framework**. The system uses a categorized prefix structure (e.g., `category: label-name`) to ensure scalability as the repository grows.

---

## 1. Category: Component
These labels identify the specific structural or logical part of the codebase affected by the issue or pull request.

### `component: backend`
*   **Purpose**: Designates issues isolated to the server-side Python codebase.
*   **Description**: Changes within the backend directory.
*   **Suggested Color**: `#1D3557` (Dark Blue)
*   **When to use**: Backend-specific bugs, dependencies, and scripts.

### `component: frontend`
*   **Purpose**: Designates issues isolated to the client-side React/TypeScript codebase.
*   **Description**: Changes within the frontend directory.
*   **Suggested Color**: `#E76F51` (Orange-Red)
*   **When to use**: Frontend components, layouts, hooks, and build tools.

### `component: shared`
*   **Purpose**: Identifies issues affecting the central contract folder.
*   **Description**: Changes to shared schemas, type sheets, or enums.
*   **Suggested Color**: `#2D6A4F` (Dark Green)
*   **When to use**: Modifying JSON schemas or core constant definitions.

### `component: simulation`
*   **Purpose**: Focuses on core clock cycles, physics loops, or spawners.
*   **Description**: Changes in engine execution or physical parameters.
*   **Suggested Color**: `#457B9D` (Steel Blue)
*   **When to use**: Tweaking clocks, active vehicle pools, or spawner logic.

### `component: controller`
*   **Purpose**: Concerns intersection control rules.
*   **Description**: Modifications to signals, roundabouts, or base interfaces.
*   **Suggested Color**: `#F4A261` (Light Orange)
*   **When to use**: Editing Fixed-Time timing phases or Roundabout yield rules.

### `component: metrics`
*   **Purpose**: Identifies work on metric collectors or calculations.
*   **Description**: Changes to efficiency or flow quality equations.
*   **Suggested Color**: `#9B5DE5` (Purple)
*   **When to use**: Adding indicators, wait thresholds, or fairness calculators.

### `component: api`
*   **Purpose**: Concerns web communications.
*   **Description**: Changes to REST endpoints, route schemas, or WebSocket stream loops.
*   **Suggested Color**: `#00F5D4` (Teal)
*   **When to use**: Adding FastAPI routers, upgrading socket routes, or CORS adjustments.

### `component: visualization`
*   **Purpose**: Focuses on canvas render pipelines.
*   **Description**: Rendering paths, vehicle coordinates, or interpolation rules.
*   **Suggested Color**: `#00BBF9` (Light Blue)
*   **When to use**: Canvas performance tweaks, panning/zooming, or vehicle rotations.

---

## 2. Category: Type
These labels describe the nature of the change or task.

### `type: bug`
*   **Purpose**: Identifies defects or failures.
*   **Description**: Something isn't working as intended.
*   **Suggested Color**: `#D73A4A` (Bright Red)
*   **When to use**: Collisions, network drop crashes, or coordinate drifts.

### `type: feature`
*   **Purpose**: Identifies new functional capabilities.
*   **Description**: Adding new modules, components, or API routers.
*   **Suggested Color**: `#0E8A16` (Green)
*   **When to use**: Creating roundabout entry codes or visual timeline sliders.

### `type: enhancement`
*   **Purpose**: Denotes improvements to existing code.
*   **Description**: Tweak or refine current behaviors.
*   **Suggested Color**: `#845EC2` (Violet)
*   **When to use**: Improving canvas coordinate rounding or linter updates.

### `type: refactor`
*   **Purpose**: Identifies structure cleanups without logic edits.
*   **Description**: Reorganizing module files or class definitions.
*   **Suggested Color**: `#D8B4F8` (Lavender)
*   **When to use**: Extracting registries or grouping metric helpers.

### `type: technical-debt`
*   **Purpose**: Identifies code quality or design cleanups.
*   **Description**: Addressing shortcuts, legacy patches, or architectural debt.
*   **Suggested Color**: `#C39BD3` (Muted Purple)
*   **When to use**: Bypassing typings or cleaning up duplicated road models.

### `type: security`
*   **Purpose**: Addresses safety or vulnerability concerns.
*   **Description**: Hardening API endpoints, CORS filters, or packages.
*   **Suggested Color**: `#111111` (Black)
*   **When to use**: Dependency warnings, input sanitization, or origin blocks.

### `type: performance`
*   **Purpose**: Targets execution speed or resource load.
*   **Description**: Optimizations for database caching or canvas loops.
*   **Suggested Color**: `#FFC300` (Yellow)
*   **When to use**: Upgrading JSON libraries or minimizing offscreen draw calls.

---

## 3. Category: Priority
These labels indicate the urgency of an issue.

### `priority: critical`
*   **Purpose**: Demands immediate developer attention.
*   **Description**: Blocks primary runs, CI compiles, or crashes builds.
*   **Suggested Color**: `#B60205` (Crimson)
*   **When to use**: Broken main branch, failing schema validators, or vehicle crashes.

### `priority: high`
*   **Purpose**: Next-in-line work item.
*   **Description**: Important milestones or key functionalities.
*   **Suggested Color**: `#D93F0B` (Rust Red)
*   **When to use**: Completing roundabout entries or WebSocket stream dropouts.

### `priority: medium`
*   **Purpose**: Standard task priority.
*   **Description**: Typical features or standard bug fixes.
*   **Suggested Color**: `#F9E79F` (Soft Yellow)
*   **When to use**: Stop count hysteresis tweaks or custom charts setup.

### `priority: low`
*   **Purpose**: Backlog or nice-to-have items.
*   **Description**: Style changes or optional document patches.
*   **Suggested Color**: `#A2D9CE` (Light Teal)
*   **When to use**: Trail rendering lengths adjustments or readme typo fixes.

---

## 4. Category: Status
These labels track the lifecycle of issues and pull requests.

### `status: blocked`
*   **Purpose**: Indicates a development block.
*   **Description**: Waiting on another PR, decision, or contract definition.
*   **Suggested Color**: `#535353` (Dark Gray)
*   **When to use**: Frontend timeline work is paused waiting on backend JSON buffers.

### `status: in-progress`
*   **Purpose**: Active work indicator.
*   **Description**: Assigned developer is currently writing code.
*   **Suggested Color**: `#F39C12` (Amber)
*   **When to use**: Feature branch created and code changes are occurring.

### `status: in-review`
*   **Purpose**: Code under evaluation.
*   **Description**: PR created and awaiting reviews.
*   **Suggested Color**: `#3498DB` (Sky Blue)
*   **When to use**: Pushed to develop and assigned reviews.

### `status: approved`
*   **Purpose**: Verified and ready to merge.
*   **Description**: Code reviews complete and checks passed.
*   **Suggested Color**: `#2ECC71` (Lime Green)
*   **When to use**: PR is ready to merge into main/develop.

### `status: needs-info`
*   **Purpose**: Stalled due to unclear requirements.
*   **Description**: Awaiting clarification or feedback.
*   **Suggested Color**: `#F5B041` (Tan)
*   **When to use**: Config ranges are out of bounds and need decisions.

### `status: ready`
*   **Purpose**: Prioritized backlog item.
*   **Description**: Open to start; requirements are clear.
*   **Suggested Color**: `#16A085` (Green-Teal)
*   **When to use**: Moved to sprint sprint backlog columns.

---

## 5. Category: Difficulty
These labels convey the expected complexity of the task.

### `difficulty: easy-win`
*   **Purpose**: Fast, simple tasks.
*   **Description**: Under 1 hour effort, low risk.
*   **Suggested Color**: `#ABEBC6` (Pale Green)
*   **When to use**: Fixing coordinate print values or adding logging files.

### `difficulty: medium`
*   **Purpose**: Average complexity.
*   **Description**: 2-4 hours effort, moderate testing.
*   **Suggested Color**: `#EDBB99` (Peach)
*   **When to use**: Adding average wait times or layout grid setups.

### `difficulty: complex`
*   **Purpose**: High complexity.
*   **Description**: Requires multiple sessions, complex tests, or contract changes.
*   **Suggested Color**: `#EC7063` (Coral)
*   **When to use**: IDM vehicle models or path overlap conflict zones.

### `difficulty: good-first-issue`
*   **Purpose**: Easy starting points for onboarding.
*   **Description**: Self-contained with clear documentation.
*   **Suggested Color**: `#70FF70` (Light Green)
*   **When to use**: Simple CSS updates or unit test fixtures.

---

## 6. Category: Technology
These labels identify the primary technical stack affected.

### `tech: python`
*   **Purpose**: Focuses on python interpreter settings.
*   **Description**: Requirements, poetry, or version upgrades.
*   **Suggested Color**: `#3572A5` (Blue-Gray)
*   **When to use**: Package updates or Pytest runner adjustments.

### `tech: react`
*   **Purpose**: Concerns React libraries.
*   **Description**: Hooks, context providers, or rendering components.
*   **Suggested Color**: `#61DAFB` (Cyan)
*   **When to use**: Layout grids or play/pause button state triggers.

### `tech: typescript`
*   **Purpose**: Concerns typings structures.
*   **Description**: Interfaces, enums, or strict compiler configurations.
*   **Suggested Color**: `#3178C6` (TypeScript Blue)
*   **When to use**: Mismatched schema models or strict compiler warnings.

### `tech: docker`
*   **Purpose**: Relates to containment files.
*   **Description**: Dockerfiles or docker-compose orchestration.
*   **Suggested Color**: `#2496ED` (Docker Blue)
*   **When to use**: Multi-stage docker updates or Nginx port maps.

### `tech: tailwind`
*   **Purpose**: Relates to styling files.
*   **Description**: Tailwind settings or design utility variables.
*   **Suggested Color**: `#06B6D4` (Tailwind Turquoise)
*   **When to use**: Adjusting layout widths or adding color tokens.

---

## 7. Category: Documentation
These labels identify issues centered on documentation.

### `docs: architecture`
*   **Purpose**: Architectural specifications.
*   **Description**: Updates to system designs, folders, or logic specifications.
*   **Suggested Color**: `#E5E7E9` (Gray-White)
*   **When to use**: Changing monorepo trees or controller specifications.

### `docs: user-guide`
*   **Purpose**: User operational guides.
*   **Description**: Updates to readmes, tutorials, or comparison templates.
*   **Suggested Color**: `#BDC3C7` (Silver)
*   **When to use**: Detailing uvicorn start scripts or docker commands.

### `docs: api-spec`
*   **Purpose**: API reference documentation.
*   **Description**: Updates to endpoints, websocket schemas, or JSON schemas.
*   **Suggested Color**: `#D5D8DC` (Light Slate)
*   **When to use**: Adding parameters to config options or modifying error codes.

---

## 8. Category: Workflow / Collaboration
These labels help organize team communications.

### `workflow: discussion`
*   **Purpose**: Requires team consensus.
*   **Description**: Design decisions or RFC discussions.
*   **Suggested Color**: `#F39C12` (Amber)
*   **When to use**: Deciding whether to use Recharts vs Chart.js.

### `workflow: research`
*   **Purpose**: Investigatory tasks.
*   **Description**: Spike issues or proof-of-concepts.
*   **Suggested Color**: `#FADBD8` (Pink)
*   **When to use**: Benchmarking Python serialization formats.

### `workflow: help-wanted`
*   **Purpose**: Open for external or team assistance.
*   **Description**: Extra hands needed to solve the issue.
*   **Suggested Color**: `#128A0C` (Dark Green)
*   **When to use**: Solving complex multi-lane conflict collision matrices.

### `workflow: duplicate`
*   **Purpose**: Administrative cleanup.
*   **Description**: Closed as duplicate of another issue.
*   **Suggested Color**: `#CCCCCC` (Light Gray)
*   **When to use**: When another issue covers the exact same scope.

### `workflow: wontfix`
*   **Purpose**: Out of scope or obsolete.
*   **Description**: Issue will be closed without modifications.
*   **Suggested Color**: `#FFFFFF` (White)
*   **When to use**: When a proposed controller violates research goals.

#!/usr/bin/env python3
"""
push_everything_to_github.py

One script to take everything currently living as local .md files / plans
and actually push it onto GitHub as real, live project state:

  1. git push          -> makes sure local commits are on origin
  2. Labels            -> 42 custom labels (component/type/priority/status/etc.)
  3. Milestones        -> 14 phase milestones
  4. Issues            -> parses docs/issues/*.md, creates 61 GitHub issues,
                          resolves "Depends on #N" references, applies
                          labels + milestone
  5. Branch protection -> protects main + develop, requires code owner
                          review + 2 approvals (enforces the "/shared/"
                          double-review rule from ADR-008 via CODEOWNERS)
  6. Project board (v2)-> creates a GitHub Projects v2 board with the 6
                          Kanban columns from kanban.md (Backlog, Ready,
                          In Progress, In Review, In Testing, Done) and
                          adds every created issue to it

Every stage is idempotent - safe to re-run if it fails partway or you add
more issues later. Each stage can be skipped independently with flags.

Requirements:
  - A GitHub Personal Access Token with scopes: repo, project
    (classic PAT) OR a fine-grained PAT with Contents, Issues, Metadata,
    Administration (for branch protection), and Projects: write.
  - Run from inside the repo (or pass --repo owner/name).
  - Only uses the Python standard library - no pip installs needed.

Usage:
  export GITHUB_TOKEN=ghp_xxx
  python push_everything_to_github.py
  python push_everything_to_github.py --skip-project --skip-branch-protection
  python push_everything_to_github.py --dry-run
"""

import os
import sys
import re
import json
import argparse
import urllib.request
import urllib.error
import subprocess

API_URL = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "Push-Everything-To-GitHub-Script",
}

# ---------------------------------------------------------------------------
# Static configuration (labels / milestones / issue ordering)
# ---------------------------------------------------------------------------

LABELS = [
    # Component
    {"name": "component: backend", "color": "1D3557", "description": "Backend-specific Python components"},
    {"name": "component: frontend", "color": "E76F51", "description": "Frontend React components"},
    {"name": "component: shared", "color": "2D6A4F", "description": "Shared JSON contracts and schemas"},
    {"name": "component: simulation", "color": "457B9D", "description": "Core physics loops and clock"},
    {"name": "component: controller", "color": "F4A261", "description": "Intersection controllers logic"},
    {"name": "component: metrics", "color": "9B5DE5", "description": "Metric calculation and aggregation"},
    {"name": "component: api", "color": "00F5D4", "description": "REST and WebSocket API endpoints"},
    {"name": "component: visualization", "color": "00BBF9", "description": "HTML5 Canvas render systems"},
    # Type
    {"name": "type: bug", "color": "D73A4A", "description": "Something isn't working"},
    {"name": "type: feature", "color": "0E8A16", "description": "New functional additions"},
    {"name": "type: enhancement", "color": "845EC2", "description": "Existing logic enhancements"},
    {"name": "type: refactor", "color": "D8B4F8", "description": "Code restructuring, no logic edits"},
    {"name": "type: technical-debt", "color": "C39BD3", "description": "Code quality or design debt updates"},
    {"name": "type: security", "color": "111111", "description": "Vulnerability or auth fixes"},
    {"name": "type: performance", "color": "FFC300", "description": "CPU/latency optimizations"},
    # Priority
    {"name": "priority: critical", "color": "B60205", "description": "Blocks primary runs, CI or main branch"},
    {"name": "priority: high", "color": "D93F0B", "description": "Important milestones or features"},
    {"name": "priority: medium", "color": "F9E79F", "description": "Standard features or bugs"},
    {"name": "priority: low", "color": "A2D9CE", "description": "Backlog items, minor doc updates"},
    # Status
    {"name": "status: blocked", "color": "535353", "description": "Waiting on another PR, decision or contract"},
    {"name": "status: in-progress", "color": "F39C12", "description": "Active development"},
    {"name": "status: in-review", "color": "3498DB", "description": "PR created and awaiting review"},
    {"name": "status: approved", "color": "2ECC71", "description": "PR approved and ready to merge"},
    {"name": "status: needs-info", "color": "F5B041", "description": "Needs design decisions or feedback"},
    {"name": "status: ready", "color": "16A085", "description": "Prioritized backlog, ready to start"},
    # Difficulty
    {"name": "difficulty: easy-win", "color": "ABEBC6", "description": "Low complexity, <1 hour"},
    {"name": "difficulty: medium", "color": "EDBB99", "description": "Average complexity, 2-4 hours"},
    {"name": "difficulty: complex", "color": "EC7063", "description": "High complexity, 1+ days"},
    {"name": "difficulty: good-first-issue", "color": "70FF70", "description": "Easy onboarding starting points"},
    # Technology
    {"name": "tech: python", "color": "3572A5", "description": "Python interpreter and package environment"},
    {"name": "tech: react", "color": "61DAFB", "description": "React libraries and hook systems"},
    {"name": "tech: typescript", "color": "3178C6", "description": "TypeScript compiler settings and typings"},
    {"name": "tech: docker", "color": "2496ED", "description": "Dockerfiles and orchestration files"},
    {"name": "tech: tailwind", "color": "06B6D4", "description": "Tailwind configuration and tokens"},
    # Documentation
    {"name": "docs: architecture", "color": "E5E7E9", "description": "System architecture design documents"},
    {"name": "docs: user-guide", "color": "BDC3C7", "description": "Readmes, tutorials, and templates"},
    {"name": "docs: api-spec", "color": "D5D8DC", "description": "REST endpoints and schema references"},
    # Workflow
    {"name": "workflow: discussion", "color": "F39C12", "description": "Requires consensus or RFC discussions"},
    {"name": "workflow: research", "color": "FADBD8", "description": "Spikes or proof-of-concept tasks"},
    {"name": "workflow: help-wanted", "color": "128A0C", "description": "Open for team assistance"},
    {"name": "workflow: duplicate", "color": "CCCCCC", "description": "Closed as duplicate"},
    {"name": "workflow: wontfix", "color": "FFFFFF", "description": "Obsolete or out of scope"},
]

MILESTONES = [
    {"title": "M1: Phase 0", "description": "Architecture complete, contract schemas, and repository setup."},
    {"title": "M2: Backend Core", "description": "Core data models, geometries, and vehicle entities."},
    {"title": "M3: Engine", "description": "Simulation loop, clock, spawner, and vehicle manager pool."},
    {"title": "M4: Logic/Phys", "description": "IDM physics, path conflict zones, base controller interface, and snapshot builder."},
    {"title": "M5: Strategies", "description": "Fixed-time signal timings, roundabout yield line thresholds, and controller registry."},
    {"title": "M6: Metrics", "description": "Collectors and calculators for operational and traffic quality indicators."},
    {"title": "M7: API Layer", "description": "FastAPI HTTP routers, endpoints, and WebSocket push stream loops."},
    {"title": "M8: FE Found", "description": "React project, design layout, API REST services, and WS clients."},
    {"title": "M9: Visuals", "description": "Canvas grid displays, road layers overlays, and vehicle rotation assets."},
    {"title": "M10: Dashboard", "description": "Live charting integrations and layout cards dashboards."},
    {"title": "M11: Integration", "description": "Scenario configuration designer forms, interpolation buffers, and timeline sliders."},
    {"title": "M12: Testing", "description": "Pytest units, integration, TestClient routes, and vitest components mocks."},
    {"title": "M13: Perf/Deploy", "description": "Pydantic serialization benchmarks, canvas speed profiles, and multi-stage Docker configs."},
    {"title": "M14: Demo", "description": "Dashboard connection badges, user manual releases, and final report comparison sheets."},
]

RECOMMENDED_ORDER = [
    "ISSUE-001", "ISSUE-004", "ISSUE-007", "ISSUE-008", "ISSUE-011", "ISSUE-015",
    "ISSUE-009", "ISSUE-010", "ISSUE-012", "ISSUE-013", "ISSUE-018", "ISSUE-020",
    "ISSUE-021", "ISSUE-014", "ISSUE-016", "ISSUE-017", "ISSUE-019", "ISSUE-022",
    "ISSUE-023", "ISSUE-024", "ISSUE-025", "ISSUE-026", "ISSUE-027", "ISSUE-028",
    "ISSUE-029", "ISSUE-030", "ISSUE-031", "ISSUE-032", "ISSUE-033", "ISSUE-034",
    "ISSUE-035", "ISSUE-036", "ISSUE-037", "ISSUE-038", "ISSUE-039", "ISSUE-040",
    "ISSUE-041", "ISSUE-042", "ISSUE-043", "ISSUE-044", "ISSUE-045", "ISSUE-051",
    "ISSUE-052", "ISSUE-002", "ISSUE-003", "ISSUE-005", "ISSUE-006", "ISSUE-046",
    "ISSUE-047", "ISSUE-048", "ISSUE-049", "ISSUE-050", "ISSUE-053", "ISSUE-054",
    "ISSUE-055", "ISSUE-056", "ISSUE-057", "ISSUE-058", "ISSUE-059", "ISSUE-060",
    "ISSUE-061",
]

# Kanban columns from docs/project-management/kanban.md
KANBAN_COLUMNS = [
    ("Backlog", "GRAY"),
    ("Ready", "BLUE"),
    ("In Progress", "YELLOW"),
    ("In Review", "ORANGE"),
    ("In Testing", "PURPLE"),
    ("Done", "GREEN"),
]

PROTECTED_BRANCHES = ["main", "develop"]

# ---------------------------------------------------------------------------
# Low level HTTP helpers
# ---------------------------------------------------------------------------


def make_request(url, method="GET", data=None):
    req = urllib.request.Request(url, method=method, headers=HEADERS)
    if data is not None:
        req.data = json.dumps(data).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return (json.loads(body) if body else {}), resp.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            err_json = json.loads(body)
            print(f"    Error {e.code}: {err_json.get('message', body)}")
            if "errors" in err_json:
                print(f"    Details: {err_json['errors']}")
        except Exception:
            print(f"    Error {e.code}: {body}")
        return None, e.code


def graphql_request(query, variables=None):
    data = {"query": query, "variables": variables or {}}
    result, status = make_request(GRAPHQL_URL, method="POST", data=data)
    if result and "errors" in result:
        print(f"    GraphQL errors: {result['errors']}")
        return None, status
    return result, status


# ---------------------------------------------------------------------------
# Repo / git helpers
# ---------------------------------------------------------------------------


def get_repo_owner_name():
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"], stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
        match = re.search(r"github\.com[:/]([^/]+)/([^.]+?)(?:\.git)?$", url)
        if match:
            return f"{match.group(1)}/{match.group(2)}"
    except Exception:
        pass
    return None


def git_push(dry_run=False):
    print("\n[0/6] Pushing local commits to origin...")
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
    except Exception as e:
        print(f"  ✗ Could not determine current branch: {e}")
        return

    status = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True
    ).stdout.strip()
    if status:
        print("  ! You have uncommitted changes. Commit them first, then re-run.")
        print(status)
        return

    if dry_run:
        print(f"  [dry-run] Would run: git push origin {branch}")
        return

    result = subprocess.run(
        ["git", "push", "origin", branch], capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"  ✓ Pushed '{branch}' to origin")
    else:
        print(f"  ✗ git push failed:\n{result.stderr}")


# ---------------------------------------------------------------------------
# Issue file parsing (unchanged logic from setup_github.py)
# ---------------------------------------------------------------------------


def parse_issue_files():
    issues = {}
    issues_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "docs", "issues"
    )
    if not os.path.exists(issues_dir):
        # Fall back to CWD-relative path in case the script is run from repo root
        issues_dir = os.path.join(os.getcwd(), "docs", "issues")

    if not os.path.exists(issues_dir):
        print(f"  ✗ Issues directory not found at {issues_dir}")
        return issues

    issue_regex = re.compile(r"## (ISSUE-\d+): (.*)")

    for file in sorted(os.listdir(issues_dir)):
        if not file.endswith(".md"):
            continue
        file_path = os.path.join(issues_dir, file)

        current_issue = None
        current_field = None
        field_content = []

        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                header_match = issue_regex.match(line.strip())
                if header_match:
                    if current_issue:
                        if current_field:
                            current_issue[current_field] = "\n".join(field_content).strip()
                        issues[current_issue["id"]] = current_issue

                    current_issue = {
                        "id": header_match.group(1),
                        "title": header_match.group(2),
                        "labels": [],
                    }
                    current_field = None
                    field_content = []
                    continue

                if current_issue is None:
                    continue

                field_match = re.match(r"^-\s+\*\*([^*]+)\*\*:\s*(.*)", line.strip())
                if field_match:
                    if current_field:
                        current_issue[current_field] = "\n".join(field_content).strip()

                    name = field_match.group(1).strip()
                    val = field_match.group(2).strip()
                    field_content = [val] if val else []

                    field_map = {
                        "Description": "description",
                        "Objective": "objective",
                        "Technical Background": "technical_background",
                        "Acceptance Criteria": "acceptance_criteria",
                        "Dependencies": "dependencies",
                        "Estimated Effort": "effort",
                        "Priority": "priority",
                        "Related Milestone": "milestone",
                        "Definition of Done": "dod",
                    }
                    if name == "Suggested Labels":
                        current_field = "suggested_labels"
                        labels_raw = re.findall(r"`([^`]+)`", val)
                        current_issue["labels"] = [l.strip() for l in labels_raw]
                    else:
                        current_field = field_map.get(name, name.lower().replace(" ", "_"))
                else:
                    if current_field:
                        field_content.append(line.rstrip())

            if current_issue:
                if current_field:
                    current_issue[current_field] = "\n".join(field_content).strip()
                issues[current_issue["id"]] = current_issue

    return issues


# ---------------------------------------------------------------------------
# Stage 1: Labels
# ---------------------------------------------------------------------------


def setup_labels(repo_url, dry_run=False):
    print("\n[1/6] Configuring GitHub Labels...")
    existing_labels, _ = make_request(f"{repo_url}/labels")
    existing_names = {l["name"] for l in existing_labels} if existing_labels else set()

    for label in LABELS:
        name = label["name"]
        if name in existing_names:
            print(f"  - '{name}' already exists, skipping")
            continue
        if dry_run:
            print(f"  [dry-run] Would create label: {name}")
            continue
        data = {"name": name, "color": label["color"], "description": label["description"]}
        res, status = make_request(f"{repo_url}/labels", method="POST", data=data)
        print(f"  {'✓' if status == 201 else '✗'} {name} ({status})")


# ---------------------------------------------------------------------------
# Stage 2: Milestones
# ---------------------------------------------------------------------------


def setup_milestones(repo_url, dry_run=False):
    print("\n[2/6] Configuring GitHub Milestones...")
    existing_milestones, _ = make_request(f"{repo_url}/milestones?state=all")
    milestone_mapping = {}
    if existing_milestones:
        for m in existing_milestones:
            milestone_mapping[m["title"]] = m["number"]

    for milestone in MILESTONES:
        title = milestone["title"]
        if title in milestone_mapping:
            print(f"  - '{title}' already exists, skipping")
            continue
        if dry_run:
            print(f"  [dry-run] Would create milestone: {title}")
            continue
        data = {"title": title, "description": milestone["description"], "state": "open"}
        res, status = make_request(f"{repo_url}/milestones", method="POST", data=data)
        if status == 201 and res:
            milestone_mapping[title] = res["number"]
        print(f"  {'✓' if status == 201 else '✗'} {title} ({status})")

    return milestone_mapping


# ---------------------------------------------------------------------------
# Stage 3: Issues
# ---------------------------------------------------------------------------


def setup_issues(repo_url, milestone_mapping, dry_run=False):
    print("\n[3/6] Parsing issue files and logging to GitHub...")
    parsed_issues = parse_issue_files()
    if not parsed_issues:
        print("  ✗ No issues parsed - skipping issue creation.")
        return {}

    print(f"  Parsed {len(parsed_issues)} issues from documentation.")

    existing_issues, _ = make_request(f"{repo_url}/issues?state=all&per_page=100")
    existing_titles = {}
    if existing_issues:
        for it in existing_issues:
            existing_titles[it["title"]] = {"number": it["number"], "node_id": it["node_id"]}

    issue_ref_mapping = {}   # ISSUE-001 -> github issue number
    issue_node_ids = []      # node ids for project board stage

    for issue_id in RECOMMENDED_ORDER:
        if issue_id not in parsed_issues:
            print(f"  ! {issue_id} not found in parsed files, skipping")
            continue

        issue = parsed_issues[issue_id]
        gh_title = f"[{issue_id}] {issue['title']}"

        if gh_title in existing_titles:
            info = existing_titles[gh_title]
            issue_ref_mapping[issue_id] = info["number"]
            issue_node_ids.append(info["node_id"])
            print(f"  - {issue_id} already exists as #{info['number']}, skipping")
            continue

        body_parts = []
        for key, heading in [
            ("description", None),
            ("objective", "Objective"),
            ("technical_background", "Technical Background"),
            ("acceptance_criteria", "Acceptance Criteria"),
            ("dod", "Definition of Done"),
        ]:
            val = issue.get(key)
            if val:
                body_parts.append(f"### {heading}\n{val}" if heading else val)

        deps_raw = issue.get("dependencies", "None").strip()
        deps_display = "None"
        if deps_raw and deps_raw != "None":
            dep_ids = re.findall(r"ISSUE-\d+", deps_raw)
            resolved = [f"#{issue_ref_mapping.get(d, d)}" for d in dep_ids]
            if resolved:
                deps_display = ", ".join(resolved)

        meta_block = (
            f"---\n- **Estimated Effort**: {issue.get('effort', 'XS')}\n"
            f"- **Priority**: {issue.get('priority', 'Medium')}\n"
            f"- **Dependencies**: {deps_display}"
        )
        body_parts.append(meta_block)
        full_body = "\n\n".join(body_parts)

        m_number = milestone_mapping.get(issue.get("milestone", ""))

        if dry_run:
            print(f"  [dry-run] Would create issue: {gh_title}")
            continue

        data = {"title": gh_title, "body": full_body, "labels": issue["labels"]}
        if m_number:
            data["milestone"] = m_number

        res, status = make_request(f"{repo_url}/issues", method="POST", data=data)
        if status == 201 and res:
            issue_ref_mapping[issue_id] = res["number"]
            issue_node_ids.append(res["node_id"])
            print(f"  ✓ {issue_id} -> #{res['number']}")
        else:
            print(f"  ✗ Failed to create {issue_id} ({status})")

    return {"ref_mapping": issue_ref_mapping, "node_ids": issue_node_ids}


# ---------------------------------------------------------------------------
# Stage 4: Branch protection (enforces ADR-008 double-review on /shared/)
# ---------------------------------------------------------------------------


def setup_branch_protection(repo_url, dry_run=False):
    print("\n[4/6] Configuring branch protection (main + develop)...")
    for branch in PROTECTED_BRANCHES:
        if dry_run:
            print(f"  [dry-run] Would protect branch: {branch}")
            continue
        data = {
            "required_status_checks": {
                "strict": True,
                "contexts": ["build-and-test"],  # adjust to match your CI job name(s)
            },
            "enforce_admins": False,
            "required_pull_request_reviews": {
                "required_approving_review_count": 2,
                "require_code_owner_reviews": True,
                "dismiss_stale_reviews": True,
            },
            "restrictions": None,
            "allow_force_pushes": False,
            "allow_deletions": False,
        }
        res, status = make_request(
            f"{repo_url}/branches/{branch}/protection", method="PUT", data=data
        )
        if status == 200:
            print(f"  ✓ Protected '{branch}' (2 approvals, CODEOWNERS required)")
        elif status == 404:
            print(f"  ! Branch '{branch}' not found on remote - skipping")
        else:
            print(f"  ✗ Failed to protect '{branch}' ({status}). "
                  f"Note: required_status_checks.contexts must match your actual CI job name.")


# ---------------------------------------------------------------------------
# Stage 5: Projects v2 board matching kanban.md
# ---------------------------------------------------------------------------


def setup_project_board(repo, owner, issue_node_ids, dry_run=False):
    print("\n[5/6] Setting up GitHub Projects (v2) Kanban board...")

    if dry_run:
        print("  [dry-run] Would create project 'Traffic Simulation Board' "
              f"with columns: {[c[0] for c in KANBAN_COLUMNS]}")
        return

    # 1. Resolve owner node id (works for both user and org accounts)
    q_owner = """
    query($login: String!) {
      repositoryOwner(login: $login) {
        id
        __typename
      }
    }
    """
    res, _ = graphql_request(q_owner, {"login": owner})
    if not res or not res.get("data", {}).get("repositoryOwner"):
        print("  ✗ Could not resolve repo owner id - skipping project board.")
        return
    owner_id = res["data"]["repositoryOwner"]["id"]

    # 2. Find existing project with this title, or create one
    title = "Traffic Simulation Board"
    project_id = None
    field_id = None

    q_existing = """
    query($login: String!) {
      repositoryOwner(login: $login) {
        ... on ProjectV2Owner {
          projectsV2(first: 20) { nodes { id title } }
        }
      }
    }
    """
    res, _ = graphql_request(q_existing, {"login": owner})
    nodes = (
        res.get("data", {}).get("repositoryOwner", {}).get("projectsV2", {}).get("nodes", [])
        if res else []
    )
    for n in nodes:
        if n["title"] == title:
            project_id = n["id"]
            print(f"  - Project '{title}' already exists, reusing it")

    if not project_id:
        m_create = """
        mutation($ownerId: ID!, $title: String!) {
          createProjectV2(input: {ownerId: $ownerId, title: $title}) {
            projectV2 { id }
          }
        }
        """
        res, status = graphql_request(m_create, {"ownerId": owner_id, "title": title})
        if not res:
            print("  ✗ Failed to create project board.")
            return
        project_id = res["data"]["createProjectV2"]["projectV2"]["id"]
        print(f"  ✓ Created project '{title}'")

    # 3. Link the repo to the project so issues can be added
    q_repo = """
    query($owner: String!, $name: String!) { repository(owner: $owner, name: $name) { id } }
    """
    res, _ = graphql_request(q_repo, {"owner": owner, "name": repo})
    repo_node_id = res["data"]["repository"]["id"] if res else None
    if repo_node_id:
        m_link = """
        mutation($projectId: ID!, $repositoryId: ID!) {
          linkProjectV2ToRepository(input: {projectId: $projectId, repositoryId: $repositoryId}) {
            repository { id }
          }
        }
        """
        graphql_request(m_link, {"projectId": project_id, "repositoryId": repo_node_id})

    # 4. Find the built-in "Status" single-select field and set its options
    #    to match the 6 kanban.md columns
    q_fields = """
    query($projectId: ID!) {
      node(id: $projectId) {
        ... on ProjectV2 {
          fields(first: 20) {
            nodes {
              ... on ProjectV2SingleSelectField { id name }
            }
          }
        }
      }
    }
    """
    res, _ = graphql_request(q_fields, {"projectId": project_id})
    if res:
        for f in res["data"]["node"]["fields"]["nodes"]:
            if f and f.get("name") == "Status":
                field_id = f["id"]

    if field_id:
        options = [{"name": name, "color": color, "description": ""} for name, color in KANBAN_COLUMNS]
        m_update_field = """
        mutation($fieldId: ID!, $options: [ProjectV2SingleSelectFieldOptionInput!]!) {
          updateProjectV2Field(input: {fieldId: $fieldId, singleSelectOptions: $options}) {
            clientMutationId
          }
        }
        """
        _, status = graphql_request(m_update_field, {"fieldId": field_id, "options": options})
        if status == 200:
            print(f"  ✓ Set Status column options: {[c[0] for c in KANBAN_COLUMNS]}")
        else:
            print("  ! Could not update Status field options - set columns manually in the UI.")
    else:
        print("  ! Could not find default 'Status' field - set up columns manually in the UI.")

    # 5. Add every created issue to the board (defaults to first column / no status)
    m_add_item = """
    mutation($projectId: ID!, $contentId: ID!) {
      addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
        item { id }
      }
    }
    """
    added = 0
    for node_id in issue_node_ids:
        res, status = graphql_request(m_add_item, {"projectId": project_id, "contentId": node_id})
        if status == 200:
            added += 1
    print(f"  ✓ Added {added}/{len(issue_node_ids)} issues to the board")
    print("  Note: newly added items default to 'Backlog'/no status - "
          "bulk-set statuses from the Projects UI if needed (fast via multi-select).")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Push everything (labels, milestones, issues, "
                                                   "branch protection, project board) to GitHub.")
    parser.add_argument("--repo", help="owner/repo, auto-detected from git remote if omitted")
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen, do nothing")
    parser.add_argument("--skip-push", action="store_true")
    parser.add_argument("--skip-labels", action="store_true")
    parser.add_argument("--skip-milestones", action="store_true")
    parser.add_argument("--skip-issues", action="store_true")
    parser.add_argument("--skip-branch-protection", action="store_true")
    parser.add_argument("--skip-project", action="store_true")
    parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    print("====================================================")
    print("     Push Everything To GitHub - Full Automation     ")
    print("====================================================")

    repo = args.repo or get_repo_owner_name()
    if not repo:
        repo = input("Enter target repository owner/name: ").strip()
    if not repo:
        print("Error: repository owner/name is required.")
        sys.exit(1)
    owner = repo.split("/")[0]
    repo_name = repo.split("/")[1]

    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token and os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if line.strip().startswith("GITHUB_TOKEN="):
                    token = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not token:
        token = input("Enter GITHUB_TOKEN (needs 'repo' + 'project' scopes): ").strip()
    if not token:
        print("Error: GITHUB_TOKEN is required.")
        sys.exit(1)

    HEADERS["Authorization"] = f"Bearer {token}"
    repo_url = f"{API_URL}/repos/{repo}"

    print(f"\nTarget repo: {repo}")
    print("This will: push commits, create labels + milestones + issues, "
          "protect main/develop, and set up a Projects board.")
    if not args.yes and not args.dry_run:
        confirm = input("Proceed? (y/n): ").strip().lower()
        if confirm != "y":
            print("Cancelled.")
            sys.exit(0)

    if not args.skip_push:
        git_push(dry_run=args.dry_run)

    if not args.skip_labels:
        setup_labels(repo_url, dry_run=args.dry_run)

    milestone_mapping = {}
    if not args.skip_milestones:
        milestone_mapping = setup_milestones(repo_url, dry_run=args.dry_run) or {}

    issue_result = {"ref_mapping": {}, "node_ids": []}
    if not args.skip_issues:
        issue_result = setup_issues(repo_url, milestone_mapping, dry_run=args.dry_run) or issue_result

    if not args.skip_branch_protection:
        setup_branch_protection(repo_url, dry_run=args.dry_run)

    if not args.skip_project:
        setup_project_board(repo_name, owner, issue_result.get("node_ids", []), dry_run=args.dry_run)

    print("\n====================================================")
    print("  Done. Check the repo's Issues, Milestones, Settings")
    print("  > Branches, and Projects tab to confirm everything.")
    print("====================================================")


if __name__ == "__main__":
    main()

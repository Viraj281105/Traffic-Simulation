#!/usr/bin/env python3
import os
import sys
import re
import json
import urllib.request
import urllib.error
import subprocess

# Strict configuration
API_URL = "https://api.github.com"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "Autonomous-GitHub-Setup-Script"
}

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
    {"name": "workflow: wontfix", "color": "FFFFFF", "description": "Obsolete or out of scope"}
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
    {"title": "M14: Demo", "description": "Dashboard connection badges, user manual releases, and final report comparison sheets."}
]

# Issue creation order (to coordinate dependencies correctly)
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
    "ISSUE-061"
]

def make_request(url, method="GET", data=None):
    req = urllib.request.Request(url, method=method, headers=HEADERS)
    if data:
        req.data = json.dumps(data).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8")), resp.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            err_json = json.loads(body)
            print(f"Error {e.code}: {err_json.get('message', body)}")
        except Exception:
            print(f"Error {e.code}: {body}")
        return None, e.code

def get_repo_owner_name():
    try:
        url = subprocess.check_output(["git", "remote", "get-url", "origin"]).decode("utf-8").strip()
        # Parse SSH or HTTPS urls
        # git@github.com:owner/repo.git or https://github.com/owner/repo.git
        match = re.search(r"github\.com[:/]([^/]+)/([^.]+)(?:\.git)?", url)
        if match:
            return f"{match.group(1)}/{match.group(2)}"
    except Exception:
        pass
    return None

def parse_issue_files():
    issues = {}
    issues_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "issues")
    
    if not os.path.exists(issues_dir):
        print(f"Error: Issues directory not found at {issues_dir}")
        return issues
        
    issue_regex = re.compile(r"## (ISSUE-\d+): (.*)")
    
    for file in os.listdir(issues_dir):
        if not file.endswith(".md"):
            continue
        file_path = os.path.join(issues_dir, file)
        
        current_issue = None
        current_field = None
        field_content = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # Detect new issue header
                header_match = issue_regex.match(line.strip())
                if header_match:
                    if current_issue:
                        # Flush current field
                        if current_field:
                            current_issue[current_field] = "\n".join(field_content).strip()
                        issues[current_issue["id"]] = current_issue
                    
                    current_issue = {
                        "id": header_match.group(1),
                        "title": header_match.group(2),
                        "labels": []
                    }
                    current_field = None
                    field_content = []
                    continue
                
                if current_issue is None:
                    continue
                
                # Check for fields
                field_match = re.match(r"^-\s+\*\*([^*]+)\*\*:\s*(.*)", line.strip())
                if field_match:
                    if current_field:
                        current_issue[current_field] = "\n".join(field_content).strip()
                    
                    name = field_match.group(1).strip()
                    val = field_match.group(2).strip()
                    
                    field_content = [val] if val else []
                    
                    if name == "Description":
                        current_field = "description"
                    elif name == "Objective":
                        current_field = "objective"
                    elif name == "Technical Background":
                        current_field = "technical_background"
                    elif name == "Acceptance Criteria":
                        current_field = "acceptance_criteria"
                    elif name == "Dependencies":
                        current_field = "dependencies"
                    elif name == "Estimated Effort":
                        current_field = "effort"
                    elif name == "Priority":
                        current_field = "priority"
                    elif name == "Suggested Labels":
                        current_field = "suggested_labels"
                        # Parse labels list
                        labels_raw = re.findall(r"`([^`]+)`", val)
                        current_issue["labels"] = [l.strip() for l in labels_raw]
                    elif name == "Related Milestone":
                        current_field = "milestone"
                    elif name == "Definition of Done":
                        current_field = "dod"
                    else:
                        current_field = name.lower().replace(" ", "_")
                else:
                    # Append details
                    if current_field:
                        # Strip markdown bullets indentations slightly if wanted, or preserve
                        field_content.append(line.rstrip())
            
            # Flush final issue of the file
            if current_issue:
                if current_field:
                    current_issue[current_field] = "\n".join(field_content).strip()
                issues[current_issue["id"]] = current_issue
                
    return issues

def setup_github_environment(token, repo):
    HEADERS["Authorization"] = f"Bearer {token}"
    repo_url = f"{API_URL}/repos/{repo}"
    
    # 1. Create Labels
    print(f"\n[1/3] Configuring GitHub Labels for {repo}...")
    # Fetch existing labels to avoid duplicates
    existing_labels, status = make_request(f"{repo_url}/labels")
    existing_names = [l["name"] for l in existing_labels] if existing_labels else []
    
    for label in LABELS:
        name = label["name"]
        if name in existing_names:
            print(f"  Label '{name}' already exists. Skipping.")
            continue
            
        data = {
            "name": name,
            "color": label["color"],
            "description": label["description"]
        }
        res, status = make_request(f"{repo_url}/labels", method="POST", data=data)
        if status == 201:
            print(f"  ✓ Created label: {name}")
        else:
            print(f"  ✗ Failed to create label: {name} (Status: {status})")

    # 2. Create Milestones
    print(f"\n[2/3] Configuring GitHub Milestones...")
    existing_milestones, status = make_request(f"{repo_url}/milestones?state=all")
    milestone_mapping = {} # title -> number
    if existing_milestones:
        for m in existing_milestones:
            milestone_mapping[m["title"]] = m["number"]

    for milestone in MILESTONES:
        title = milestone["title"]
        if title in milestone_mapping:
            print(f"  Milestone '{title}' already exists. Skipping.")
            continue
            
        data = {
            "title": title,
            "description": milestone["description"],
            "state": "open"
        }
        res, status = make_request(f"{repo_url}/milestones", method="POST", data=data)
        if status == 201 and res:
            milestone_mapping[title] = res["number"]
            print(f"  ✓ Created milestone: {title}")
        else:
            print(f"  ✗ Failed to create milestone: {title} (Status: {status})")

    # 3. Parse and Create Issues
    print(f"\n[3/3] Parsing issues and logging to GitHub...")
    parsed_issues = parse_issue_files()
    if not parsed_issues:
        print("No issues parsed. Exiting.")
        return
        
    print(f"  Parsed {len(parsed_issues)} issues from documentation.")
    
    # Store mapping of ISSUE-001 -> GitHub Issue Number (#1)
    issue_ref_mapping = {}
    
    for issue_id in RECOMMENDED_ORDER:
        if issue_id not in parsed_issues:
            print(f"Warning: Issue {issue_id} not found in parsed files. Skipping.")
            continue
            
        issue = parsed_issues[issue_id]
        
        # Build Body
        body_parts = []
        if issue.get("description"):
            body_parts.append(issue["description"])
            
        if issue.get("objective"):
            body_parts.append(f"### Objective\n{issue['objective']}")
            
        if issue.get("technical_background"):
            body_parts.append(f"### Technical Background\n{issue['technical_background']}")
            
        if issue.get("acceptance_criteria"):
            body_parts.append(f"### Acceptance Criteria\n{issue['acceptance_criteria']}")
            
        if issue.get("dod"):
            body_parts.append(f"### Definition of Done\n{issue['dod']}")
            
        # Dependencies block
        deps_raw = issue.get("dependencies", "None").strip()
        deps_display = "None"
        if deps_raw and deps_raw != "None":
            dep_ids = re.findall(r"ISSUE-\d+", deps_raw)
            resolved_deps = []
            for d in dep_ids:
                actual_num = issue_ref_mapping.get(d)
                if actual_num:
                    resolved_deps.append(f"#{actual_num}")
                else:
                    resolved_deps.append(d)
            if resolved_deps:
                deps_display = ", ".join(resolved_deps)
                
        meta_block = f"---\n- **Estimated Effort**: {issue.get('effort', 'XS')}\n- **Priority**: {issue.get('priority', 'Medium')}\n- **Dependencies**: {deps_display}"
        body_parts.append(meta_block)
        
        full_body = "\n\n".join(body_parts)
        
        # Resolve milestone number
        m_title = issue.get("milestone", "")
        m_number = milestone_mapping.get(m_title)
        
        # Determine assignees
        assignees = []
        raw_assignee = issue.get("suggested_assignee", "").strip().lower()
        if "backend" in raw_assignee:
            assignees.append("virajjadhao")
        elif "frontend" in raw_assignee:
            assignees.append("khushikashyap-sas")
        elif "both" in raw_assignee or "shared" in raw_assignee:
            assignees.append("virajjadhao")
            assignees.append("khushikashyap-sas")

        data = {
            "title": f"[{issue_id}] {issue['title']}",
            "body": full_body,
            "labels": issue["labels"]
        }
        if assignees:
            data["assignees"] = assignees
        if m_number:
            data["milestone"] = m_number
            
        res, status = make_request(f"{repo_url}/issues", method="POST", data=data)
        if status == 201 and res:
            git_num = res["number"]
            issue_ref_mapping[issue_id] = git_num
            print(f"  ✓ Logged {issue_id} as GitHub Issue #{git_num}")
        else:
            print(f"  ✗ Failed to log {issue_id} (Status: {status})")

    print("\nGitHub Environment Setup Completed Successfully!")

def main():
    print("====================================================")
    print("  Traffic Intersection Control Comparison Framework  ")
    print("         GitHub Environment Setup Automation         ")
    print("====================================================\n")
    
    # Auto-detect repository
    detected_repo = get_repo_owner_name()
    if detected_repo:
        print(f"Auto-detected repository: {detected_repo}")
    else:
        detected_repo = ""
        
    repo = input(f"Enter target repository owner/name [{detected_repo}]: ").strip()
    if not repo:
        repo = detected_repo
        
    if not repo:
        print("Error: Target repository owner/name is required.")
        sys.exit(1)
        
    # Get GITHUB_TOKEN
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        # Try checking .env file
        if os.path.exists(".env"):
            with open(".env", "r") as f:
                for line in f:
                    if line.strip().startswith("GITHUB_TOKEN="):
                        token = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                        break
                        
    if not token:
        token = input("Enter GITHUB_TOKEN (Personal Access Token): ").strip()
        
    if not token:
        print("Error: GITHUB_TOKEN is required to execute API updates.")
        sys.exit(1)
        
    confirm = input(f"\nThis script will create labels, milestones, and 61 issues in {repo}.\nProceed? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Execution cancelled.")
        sys.exit(0)
        
    setup_github_environment(token, repo)

if __name__ == "__main__":
    main()

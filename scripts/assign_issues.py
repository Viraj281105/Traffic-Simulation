#!/usr/bin/env python3
import os
import re
import sys

# Reuse headers and methods from setup_github
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from setup_github import (
    API_URL,
    HEADERS,
    get_repo_owner_name,
    make_request,
    parse_issue_files,
)


def assign_existing_issues(token, repo):
    HEADERS["Authorization"] = f"Bearer {token}"
    repo_url = f"{API_URL}/repos/{repo}"

    print(f"Fetching open and closed issues for {repo}...")
    
    # Fetch issues in pages (max 100 per page)
    existing_issues = []
    page = 1
    while True:
        url = f"{repo_url}/issues?state=all&per_page=100&page={page}"
        issues, status = make_request(url)
        if not issues:
            break
        existing_issues.extend(issues)
        if len(issues) < 100:
            break
        page += 1

    print(f"Found {len(existing_issues)} issues in remote repository.")

    parsed_issues = parse_issue_files()
    if not parsed_issues:
        print("No issues parsed from local files.")
        return

    updated_count = 0
    
    for gh_issue in existing_issues:
        title = gh_issue["title"]
        # Match pattern [ISSUE-XXX]
        match = re.match(r"^\[(ISSUE-\d+)\]", title)
        if not match:
            continue
            
        issue_id = match.group(1)
        if issue_id not in parsed_issues:
            continue
            
        issue = parsed_issues[issue_id]
        
        # Determine target assignees
        assignees = []
        raw_assignee = issue.get("suggested_assignee", "").strip().lower()
        if "backend" in raw_assignee:
            assignees.append("virajjadhao")
        elif "frontend" in raw_assignee:
            assignees.append("khushikashyap-sas")
        elif "both" in raw_assignee or "shared" in raw_assignee:
            assignees.append("virajjadhao")
            assignees.append("khushikashyap-sas")
            
        # Check current assignees
        current_logins = [a["login"] for a in gh_issue.get("assignees", [])]
        
        # If already assigned correctly, skip
        if sorted(assignees) == sorted(current_logins):
            continue
            
        print(f"Assigning #{gh_issue['number']} ({issue_id}) -> {assignees}")
        
        patch_url = f"{repo_url}/issues/{gh_issue['number']}"
        data = {"assignees": assignees}
        _, status = make_request(patch_url, method="PATCH", data=data)
        if status == 200:
            updated_count += 1
            
    print(f"\nSuccessfully updated {updated_count} issues.")

def main():
    detected_repo = get_repo_owner_name() or ""
    prompt = f"Enter target repository owner/name [{detected_repo}]: "
    repo = input(prompt).strip() or detected_repo
    if not repo:
        print("Error: Target repository is required.")
        sys.exit(1)
        
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token and os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if line.strip().startswith("GITHUB_TOKEN="):
                    token = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not token:
        token = input("Enter GITHUB_TOKEN (Personal Access Token): ").strip()
        
    if not token:
        print("Error: GITHUB_TOKEN is required.")
        sys.exit(1)
        
    assign_existing_issues(token, repo)

if __name__ == "__main__":
    main()

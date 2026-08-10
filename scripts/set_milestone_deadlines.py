import os
import datetime
import json
import urllib.request
import urllib.error

token = os.environ.get("GITHUB_TOKEN")
repo = "Viraj281105/Traffic-Simualtion"
headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "Mozilla/5.0",
}

# 10 Consolidated Milestones with their target working day efforts
MILESTONES = [
    {"title": "M1: Phase 0 - Setup & Architecture", "description": "Repository setup, architectural specifications, and linters configurations.", "days": 3},
    {"title": "M2: Backend Core - Geometries & Entities", "description": "Core data models, road entities, and vehicle components.", "days": 4},
    {"title": "M3: Engine - Simulation Loop & Pool", "description": "Simulation clock, execution loop, vehicle spawner, and pool manager.", "days": 5},
    {"title": "M4: Logic/Phys - IDM & Conflict Zones", "description": "IDM physics, intersection geometry connector routes, and collision prevention.", "days": 6},
    {"title": "M5: Strategies - Signals & Roundabout", "description": "Fixed-time signal cycles and modern roundabout yielding thresholds.", "days": 6},
    {"title": "M6: Metrics - Calculators & Snapshots", "description": "Traffic metrics calculators and snapshot serialization history buffers.", "days": 5},
    {"title": "M7: API Layer - FastAPI & WebSockets", "description": "REST endpoints, CORS rules, and real-time WebSocket state streams.", "days": 4},
    {"title": "M8: FE Found - React Setup & Services", "description": "React TS framework, design tokens, layout structures, and API REST/WS clients.", "days": 4},
    {"title": "M9: Visuals - Canvas Render & Overlay", "description": "HTML5 Canvas viewport scaling, road overlays, and heading-rotated vehicle assets.", "days": 4},
    {"title": "M10: Dashboard - Integration & Polish", "description": "Live charting dashboards, scenario configurations, and performance tuning.", "days": 4}
]

def add_working_days(start_date, days):
    current_date = start_date
    added_days = 0
    while added_days < days:
        current_date += datetime.timedelta(days=1)
        if current_date.weekday() < 5:  # Monday to Friday
            added_days += 1
    return current_date

def make_request(url, method="GET", data=None):
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, method=method, headers=headers, data=body)
    try:
        with urllib.request.urlopen(req) as res:
            return json.loads(res.read().decode("utf-8")), res.status
    except urllib.error.HTTPError as e:
        print(f"Error: {e.status} - {e.read().decode('utf-8')}")
        return None, e.status

def main():
    if not token or token == "your_real_github_pat":
        print("Please replace 'your_real_github_pat' with your actual GitHub PAT.")
        return
    
    repo_url = f"https://api.github.com/repos/{repo}"
    
    # Fetch existing milestones
    existing, status = make_request(f"{repo_url}/milestones?state=all")
    mapping = {m["title"]: m["number"] for m in existing} if existing else {}
    
    # Start date is Monday, August 10, 2026
    current_date = datetime.datetime(2026, 8, 10, tzinfo=datetime.timezone.utc)
    
    for ms in MILESTONES:
        title = ms["title"]
        # Calculate target due date adding working days sequentially
        current_date = add_working_days(current_date, ms["days"])
        due_str = current_date.strftime("%Y-%m-%dT23:59:59Z")
        
        data = {
            "title": title,
            "description": ms["description"],
            "state": "open",
            "due_on": due_str
        }
        
        if title in mapping:
            num = mapping[title]
            print(f"Updating Milestone '{title}' with due date {due_str}...")
            make_request(f"{repo_url}/milestones/{num}", method="PATCH", data=data)
        else:
            print(f"Creating Milestone '{title}' with due date {due_str}...")
            make_request(f"{repo_url}/milestones", method="POST", data=data)

if __name__ == "__main__":
    main()

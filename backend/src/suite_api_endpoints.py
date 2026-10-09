
# ── Scenario Suites (V1.7) ──────────────────────────────────────────────────

class ScenarioSuiteCreate(BaseModel):
    name: str
    description: str
    run_ids: list[str]
    config_variations: Dict[str, Any]

@app.post("/api/suites")
def create_suite(
    suite_data: ScenarioSuiteCreate,
    user_id: Optional[str] = Depends(get_current_user_id),
):
    suite_id = str(uuid.uuid4())
    with get_db_connection() as conn:
        ScenarioSuiteDAO.save(
            conn,
            suite_id=suite_id,
            name=suite_data.name,
            description=suite_data.description,
            run_ids=suite_data.run_ids,
            config_variations=suite_data.config_variations
        )
    return {"id": suite_id}


@app.get("/api/suites")
def list_suites(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: Optional[str] = Depends(get_current_user_id),
):
    with get_db_connection() as conn:
        suites = ScenarioSuiteDAO.list_suites(conn, limit, offset)
        return {"suites": suites}


@app.get("/api/suites/{suite_id}")
def get_suite(
    suite_id: str,
    user_id: Optional[str] = Depends(get_current_user_id),
):
    with get_db_connection() as conn:
        suite = ScenarioSuiteDAO.get(conn, suite_id)
        if not suite:
            raise HTTPException(status_code=404, detail="Suite not found")
        # Fetch actual run records for the suite
        runs = []
        for rid in suite["run_ids"]:
            r = SimulationRunDAO.get(conn, rid)
            if r:
                runs.append(r)
        return {"suite": suite, "runs": runs}

@app.post("/api/suites/{suite_id}/batch")
def enqueue_suite_batch(
    suite_id: str,
    user_id: Optional[str] = Depends(get_current_user_id),
):
    raise HTTPException(status_code=501, detail="Not implemented")


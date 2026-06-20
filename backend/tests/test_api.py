"""HTTP-layer tests for the FastAPI app.

These exercise the API through the real request/response stack (unlike
test_engine.py, which calls build_plan() directly). They exist primarily to
guard against a regression where `from __future__ import annotations` in
main.py, combined with the slowapi rate-limit decorator, made FastAPI treat
the request body `inp: PlanInput` as a (missing) query parameter and return
422 on every /api/plan call — a failure invisible to the engine-level tests.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

VALID_REQUEST = {
    "persons": [{"name": "Sam", "current_age": 55, "retirement_age": 65,
                 "death_age": 92, "ss_monthly_at_fra": 2800, "ss_claim_age": 67}],
    "accounts": [{"name": "401k", "type": "tax_deferred", "owner": 0,
                  "balance": 850_000, "annual_contribution": 30_000}],
    "annual_spending": 80_000,
    "assumptions": {"roth_conversion_strategy": "none"},
}


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_plan_endpoint_accepts_json_body():
    # Regression: must read the POSTed body, not look for a query param.
    r = client.post("/api/plan", json=VALID_REQUEST)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "metrics" in body
    assert "nest_egg_at_retirement" in body["metrics"]


def test_plan_endpoint_validates_input():
    # A malformed body should be a 422 about the body, not a server error.
    r = client.post("/api/plan", json={"persons": []})
    assert r.status_code == 422


def test_plan_excel_endpoint_returns_xlsx():
    r = client.post("/api/plan/excel", json=VALID_REQUEST)
    assert r.status_code == 200, r.text
    assert "spreadsheetml" in r.headers.get("content-type", "")
    assert r.content[:2] == b"PK"  # valid zip/xlsx

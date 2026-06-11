"""FastAPI app exposing the projection engine.

POST /api/plan        -> full PlanResult JSON
POST /api/plan/excel  -> auditable .xlsx workbook (same inputs)
GET  /health          -> liveness probe
"""
from __future__ import annotations

import io

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .engine.excel import build_workbook
from .engine.planner import build_plan
from .models import PlanInput, PlanResult

app = FastAPI(
    title="Retirement Planner Engine",
    description="Deterministic, auditable retirement projection engine. "
                "All statutory parameters are cited in the Assumptions sheet "
                "of the Excel export and in backend/app/engine/constants.py.",
    version="1.0.0",
)

# The app is a stateless, no-auth calculator shown on an advisor's screen;
# the API serves a single known frontend but carries no user secrets.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/plan", response_model=PlanResult)
def plan(inp: PlanInput) -> PlanResult:
    return build_plan(inp)


@app.post("/api/plan/excel")
def plan_excel(inp: PlanInput) -> StreamingResponse:
    result = build_plan(inp)
    data = build_workbook(inp, result)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="retirement-plan-audit.xlsx"'},
    )

"""FastAPI app exposing the projection engine.

POST /api/plan        -> full PlanResult JSON
POST /api/plan/excel  -> auditable .xlsx workbook (same inputs)
GET  /health          -> liveness probe

NOTE: do NOT add `from __future__ import annotations` here. Under PEP 563 the
endpoint annotations become strings, and combined with the slowapi rate-limit
decorator FastAPI fails to resolve `inp: PlanInput` as the request body and
treats it as a (missing) query parameter, returning 422 on every call. The
HTTP-layer test in tests/test_api.py guards against this regression.
"""
import io

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

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

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/health")
def health() -> dict:
    # build_marker lets a deploy be verified from the outside: bump this string
    # any time you need to confirm a specific commit actually redeployed rather
    # than an old container answering health checks.
    return {"status": "ok", "build_marker": "healthcare-gross-fix-2026-07-01-v2"}


@app.get("/api/constants/freshness")
def get_constants_freshness() -> list[dict]:
    """Per-group freshness: last_updated date, update cycle, and whether the
    value is likely due for review based on calendar logic."""
    from .engine.constants import constants_freshness
    return constants_freshness()


@app.post("/api/plan", response_model=PlanResult)
@limiter.limit("10/minute")
def plan(request: Request, inp: PlanInput) -> PlanResult:
    return build_plan(inp)


@app.post("/api/plan/excel")
@limiter.limit("10/minute")
def plan_excel(request: Request, inp: PlanInput) -> StreamingResponse:
    result = build_plan(inp)
    data = build_workbook(inp, result)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="retirement-plan-audit.xlsx"'},
    )
